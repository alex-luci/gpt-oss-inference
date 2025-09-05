#!/usr/bin/env python3
import requests
import json
import sys
import os

CONVERSATION_FILE = "conversation_history.json"

def load_conversation():
    """Load existing conversation history"""
    if os.path.exists(CONVERSATION_FILE):
        with open(CONVERSATION_FILE, 'r') as f:
            return json.load(f)
    return []

def save_conversation(messages):
    """Save conversation history"""
    with open(CONVERSATION_FILE, 'w') as f:
        json.dump(messages, f, indent=2)

def chat_with_memory(message, clear_history=False):
    """Chat with conversation memory"""
    
    # Load or clear conversation history
    if clear_history:
        messages = []
        if os.path.exists(CONVERSATION_FILE):
            os.remove(CONVERSATION_FILE)
        print("Conversation history cleared!")
        return
    else:
        messages = load_conversation()
    
    # Add user message
    messages.append({"role": "user", "content": message})
    
    # Make API call with full conversation history
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": "gpt-oss:20b",
        "messages": messages,
        "stream": False,
        "keep_alive": "10m"
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            assistant_response = response.json()['message']['content']
            
            # Add assistant response to history
            messages.append({"role": "assistant", "content": assistant_response})
            
            # Save updated conversation
            save_conversation(messages)
            
            print(f"Response: {assistant_response}")
            return assistant_response
        else:
            print(f"Error: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def show_history():
    """Show conversation history"""
    messages = load_conversation()
    if not messages:
        print("No conversation history found.")
        return
    
    print("Conversation History:")
    print("=" * 50)
    for i, msg in enumerate(messages):
        role = msg['role'].title()
        content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
        print(f"{i+1}. {role}: {content}")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} 'your message'")
        print(f"  {sys.argv[0]} --clear      # Clear conversation history")
        print(f"  {sys.argv[0]} --history    # Show conversation history")
        return
    
    if sys.argv[1] == "--clear":
        chat_with_memory("", clear_history=True)
    elif sys.argv[1] == "--history":
        show_history()
    else:
        message = sys.argv[1]
        chat_with_memory(message)

if __name__ == "__main__":
    main()
