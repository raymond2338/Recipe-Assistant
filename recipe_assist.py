import os
import streamlit as st
from typing import List, Optional, Dict
import json
from mistralai import Mistral
import requests


class RecipeAssistant:
    """Assistant for handling recipe queries and general chat."""

    def __init__(self, mistral_api_key: str, spoonacular_api_key: str):
        self.mistral_client = Mistral(api_key=mistral_api_key)
        self.spoonacular_api_key = spoonacular_api_key
        self.base_url = "https://api.spoonacular.com/recipes/complexSearch"

    def chat(self, message: str) -> str:
        """Handle regular conversation."""
        try:
            response = self.mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": message}]
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Chat error: {e}")

    def is_recipe_query(self, message: str) -> bool:
        """Check if the message is recipe-related."""
        try:
            prompt = f"""Determine if this message is asking about recipes, cooking, food, or ingredients. 
            Respond with just 'true' or 'false': {message}"""
            response = self.mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.lower().strip() == "true"
        except Exception as e:
            raise Exception(f"Error determining recipe query: {e}")

    def search_recipes(self, **kwargs) -> Dict:
        """Search for recipes based on criteria."""
        params = {
            'apiKey': self.spoonacular_api_key,
            'addRecipeInformation': True,
            'fillIngredients': True,
            'number': 5
        }
        # Add optional parameters
        for key, value in kwargs.items():
            if value:
                if isinstance(value, list):
                    params[key] = ','.join(value)
                else:
                    params[key] = value

        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching recipes: {e}")

    def get_recipe_details(self, recipe_id: int) -> Dict:
        """Get detailed information about a specific recipe."""
        url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
        params = {'apiKey': self.spoonacular_api_key}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching recipe details: {e}")

def process_message(message: str, assistant: RecipeAssistant):
    """Process user message and determine response type."""
    if not message.strip():
        raise ValueError("Message cannot be empty.")

    try:
        is_recipe = assistant.is_recipe_query(message)
        if is_recipe:
            # Attempt to interpret recipe-related queries
            response = assistant.mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": message}],
                tools=tools,
                tool_choice="auto"
            )
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = json.loads(tool_call.function.arguments)
            results = assistant.search_recipes(**function_args)
            return response.choices[0].message.content, results, True
        else:
            # Respond politely to non-food-related queries
            return "I'm here to assist with food, recipes, and cooking-related questions only. Please ask me something related to food!", None, False
    except Exception as e:
        raise Exception(f"Error processing message: {str(e)}")

def main():
    """Streamlit UI setup and app entry point."""
    st.set_page_config(page_title="AI Recipe Assistant", page_icon="🍳", layout="wide")

    st.title("🍳 AI Recipe Assistant")
    st.write("I'm here to help with recipes, cooking tips, and food-related queries!")

    mistral_api_key = st.sidebar.text_input("Mistral API Key", type="password")
    spoonacular_api_key = st.sidebar.text_input("Spoonacular API Key", type="password")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if "results" in message:
                results = message["results"]
                if results and results.get('results'):
                    st.subheader("📋 Found Recipes:")
                    cols = st.columns(len(results['results']))
                    for idx, recipe in enumerate(results['results']):
                        with cols[idx]:
                            st.image(recipe.get('image'), use_column_width=True)
                            st.markdown(f"**{recipe['title']}**")
                            st.write(f"Ready in: {recipe['readyInMinutes']} minutes")
                            st.write(f"Servings: {recipe['servings']}")
                            st.write(f"[View Recipe]({recipe['sourceUrl']})")

    if prompt := st.chat_input("Ask me about food or recipes!"):
        if not mistral_api_key or not spoonacular_api_key:
            st.error("Please enter your API keys in the sidebar to continue.")
            return

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        assistant = RecipeAssistant(mistral_api_key, spoonacular_api_key)
        try:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response, results, is_recipe = process_message(prompt, assistant)
                    st.write(response)
                    if is_recipe and results and results.get('results'):
                        st.subheader("📋 Found Recipes:")
                        cols = st.columns(len(results['results']))
                        for idx, recipe in enumerate(results['results']):
                            with cols[idx]:
                                st.image(recipe.get('image'), use_column_width=True)
                                st.markdown(f"**{recipe['title']}**")
                                st.write(f"Ready in: {recipe['readyInMinutes']} minutes")
                                st.write(f"Servings: {recipe['servings']}")
                                st.write(f"[View Recipe]({recipe['sourceUrl']})")
            st.session_state.messages.append({"role": "assistant", "content": response, "results": results if is_recipe else None})

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
