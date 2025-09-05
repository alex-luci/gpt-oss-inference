#!/usr/bin/env python3
import ollama
import requests
import json
import sys

def chat_with_ollama(model_name, message, unload_after=False):
    """
    Chat with Ollama model and optionally unload it after
    """
    try:
        # Make the chat request
        response = ollama.chat(
            model=model_name,
            messages=[{'role': 'user', 'content': message}]
        )
        
        result = response['message']['content']
        print(f"Response: {result}")
        
        # Optionally unload the model to free VRAM
        if unload_after:
            unload_model(model_name)
            
        return result
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def unload_model(model_name):
    """
    Unload model from VRAM using Ollama API
    """
    try:
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": model_name,
            "keep_alive": 0  # This unloads the model immediately
        }
        
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"Model {model_name} unloaded from VRAM")
        else:
            print(f"Failed to unload model: {response.status_code}")
            
    except Exception as e:
        print(f"Error unloading model: {e}")

def list_models():
    """
    List available models
    """
    try:
        models = ollama.list()
        print("Available models:")
        for model in models['models']:
            print(f"  - {model['name']}")
    except Exception as e:
        print(f"Error listing models: {e}")

def main():
    model_name = "gpt-oss:20b"
    
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} 'your message here'")
        print(f"  {sys.argv[0]} 'your message here' --unload")
        print(f"  {sys.argv[0]} --list")
        return
    
    if sys.argv[1] == "--list":
        list_models()
        return
    
    message = sys.argv[1]
    unload_after = "--unload" in sys.argv
    
    chat_with_ollama(model_name, message, unload_after)

if __name__ == "__main__":
    main()
