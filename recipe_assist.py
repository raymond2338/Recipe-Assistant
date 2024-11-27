import os
import streamlit as st
from typing import List, Optional, Dict
import json
from mistralai import Mistral
import requests

class RecipeAssistant:
    def __init__(self, mistral_api_key: str, spoonacular_api_key: str):
        self.mistral_client = Mistral(api_key=mistral_api_key)
        self.spoonacular_api_key = spoonacular_api_key
        self.base_url = "https://api.spoonacular.com/recipes/complexSearch"
    
    def chat(self, message: str) -> str:
        """Handle regular conversation"""
        response = self.mistral_client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": message}]
        )
        return response.choices[0].message.content

    def is_recipe_query(self, message: str) -> bool:
        """Check if the message is recipe-related"""
        prompt = f"""Determine if this message is asking about recipes, cooking, food, or ingredients. 
        Respond with just 'true' or 'false': {message}"""
        
        response = self.mistral_client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.lower().strip() == "true"

    def search_recipes(self, 
                      ingredients: Optional[List[str]] = None,
                      cuisine: Optional[str] = None,
                      diet: Optional[str] = None,
                      intolerances: Optional[List[str]] = None,
                      meal_type: Optional[str] = None,
                      max_ready_time: Optional[int] = None,
                      min_protein: Optional[int] = None,
                      max_calories: Optional[int] = None,
                      sort: Optional[str] = None) -> Dict:
        params = {
            'apiKey': self.spoonacular_api_key,
            'addRecipeInformation': True,
            'fillIngredients': True,
            'number': 5
        }
        
        if ingredients:
            params['includeIngredients'] = ','.join(ingredients)
        if cuisine:
            params['cuisine'] = cuisine
        if diet:
            params['diet'] = diet
        if intolerances:
            params['intolerances'] = ','.join(intolerances)
        if meal_type:
            params['type'] = meal_type
        if max_ready_time:
            params['maxReadyTime'] = max_ready_time
        if min_protein:
            params['minProtein'] = min_protein
        if max_calories:
            params['maxCalories'] = max_calories
        if sort:
            params['sort'] = sort
            
        response = requests.get(self.base_url, params=params)
        return response.json()

    def get_recipe_details(self, recipe_id: int) -> Dict:
        url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
        params = {'apiKey': self.spoonacular_api_key}
        response = requests.get(url, params=params)
        return response.json()

# Function specifications for Mistral
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_recipes",
            "description": "Search for recipes based on ingredients and other criteria",
            "parameters": {
                "type": "object",
                "properties": {
                    "ingredients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ingredients to include in the recipe"
                    },
                    "cuisine": {
                        "type": "string",
                        "description": "Type of cuisine (e.g., Italian, Chinese, Mexican)",
                        "enum": ["African", "American", "British", "Cajun", "Caribbean", "Chinese", "Eastern European", 
                                "European", "French", "German", "Greek", "Indian", "Irish", "Italian", "Japanese", 
                                "Jewish", "Korean", "Latin American", "Mediterranean", "Mexican", "Middle Eastern", 
                                "Nordic", "Southern", "Spanish", "Thai", "Vietnamese"]
                    },
                    "diet": {
                        "type": "string",
                        "description": "Special diet restrictions",
                        "enum": ["Gluten Free", "Ketogenic", "Vegetarian", "Vegan", "Pescetarian", "Paleo", 
                                "Primal", "Low FODMAP", "Whole30"]
                    },
                    "intolerances": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of intolerances",
                        "enum": ["Dairy", "Egg", "Gluten", "Grain", "Peanut", "Seafood", "Sesame", "Shellfish", 
                                "Soy", "Sulfite", "Tree Nut", "Wheat"]
                    },
                    "meal_type": {
                        "type": "string",
                        "description": "Type of meal",
                        "enum": ["main course", "side dish", "dessert", "appetizer", "salad", "bread", "breakfast", 
                                "soup", "beverage", "sauce", "marinade", "fingerfood", "snack", "drink"]
                    },
                    "max_ready_time": {
                        "type": "integer",
                        "description": "Maximum time to prepare the recipe (in minutes)"
                    },
                    "min_protein": {
                        "type": "integer",
                        "description": "Minimum amount of protein in grams"
                    },
                    "max_calories": {
                        "type": "integer",
                        "description": "Maximum calories per serving"
                    },
                    "sort": {
                        "type": "string",
                        "description": "How to sort the results",
                        "enum": ["popularity", "healthiness", "price", "time", "random", "max-used-ingredients", 
                                "min-missing-ingredients", "alcohol", "caffeine", "energy", "protein", "fat", "carbs"]
                    }
                }
            }
        }
    }
]

def process_message(message: str, assistant: RecipeAssistant):
    """Process user message and determine whether to chat or search recipes"""
    try:
        # First, check if it's a recipe query
        is_recipe = assistant.is_recipe_query(message)
        
        if is_recipe:
            # Process as recipe query
            messages = [{"role": "user", "content": message}]
            
            response = assistant.mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = json.loads(tool_call.function.arguments)
            
            results = assistant.search_recipes(**function_args)
            
            messages.extend([
                response.choices[0].message,
                {
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": json.dumps(results),
                    "tool_call_id": tool_call.id
                }
            ])
            
            final_response = assistant.mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=messages
            )
            
            return final_response.choices[0].message.content, results, True
        else:
            # Process as regular chat
            chat_response = assistant.chat(message)
            return chat_response, None, False
            
    except Exception as e:
        raise Exception(f"Error processing message: {str(e)}")

def main():
    st.set_page_config(page_title="AI Recipe Assistant", layout="wide")
    
    st.title("🍳 AI Recipe Assistant")
    st.write("Chat with me about anything! I can help you find recipes or just have a friendly conversation.")

    # Sidebar for API keys
    st.sidebar.title("Configuration")
    mistral_api_key = st.sidebar.text_input("Mistral API Key", type="password")
    spoonacular_api_key = st.sidebar.text_input("Spoonacular API Key", type="password")

    # Initialize session state for storing conversation history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if "results" in message:
                # Display recipe results
                results = message["results"]
                if results and 'results' in results and results['results']:
                    st.subheader("📋 Found Recipes:")
                    cols = st.columns(len(results['results']))
                    for idx, recipe in enumerate(results['results']):
                        with cols[idx]:
                            # st.image(recipe['image'], use_column_width=True)
                            st.write(f"**{recipe['title']}**")
                            st.write(f"Ready in: {recipe['readyInMinutes']} minutes")
                            st.write(f"Servings: {recipe['servings']}")
                            st.write(f"[View Recipe]({recipe['sourceUrl']})")

    # Chat input
    if prompt := st.chat_input("Chat with me or ask about recipes!"):
        if not mistral_api_key:
            st.error("Please enter your Mistral API key in the sidebar to continue.")
            return

        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # Process the message
        try:
            assistant = RecipeAssistant(mistral_api_key, spoonacular_api_key)
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response, results, is_recipe = process_message(prompt, assistant)
                    
                    # Display response
                    st.write(response)
                    
                    # If it's a recipe query and we have results, display them
                    if is_recipe and results and 'results' in results and results['results']:
                        st.subheader("📋 Found Recipes:")
                        cols = st.columns(len(results['results']))
                        for idx, recipe in enumerate(results['results']):
                            with cols[idx]:
                                # st.image(recipe['image'], use_column_width=True)
                                st.markdown(f"**{recipe['title']}**")
                                st.write(f"Ready in: {recipe['readyInMinutes']} minutes")
                                st.write(f"Servings: {recipe['servings']}")
                                st.write(f"[View Recipe]({recipe['sourceUrl']})")

            # Add assistant response to chat history
            response_message = {"role": "assistant", "content": response}
            if is_recipe and results:
                response_message["results"] = results
            st.session_state.messages.append(response_message)

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()