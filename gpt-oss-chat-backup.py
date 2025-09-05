#!/usr/bin/env python3
import requests
import json
import sys

def some_fcn(msg):
    """Example tool function that prints a message"""
    print(f"🔧 Tool executed: {msg}")
    return f"Tool 'some_fcn' executed with message: {msg}"

def get_weather(location):
    """Get weather information for a location"""
    # Simulate weather API call
    weather_data = {
        "location": location,
        "temperature": "22°C",
        "condition": "Sunny",
        "humidity": "65%"
    }
    return f"Weather in {location}: {weather_data['temperature']}, {weather_data['condition']}, Humidity: {weather_data['humidity']}"

def calculate(expression):
    """Safely evaluate a mathematical expression"""
    try:
        # Only allow basic math operations for safety
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expression):
            return "Error: Only basic math operations are allowed"
        
        result = eval(expression)
        return f"Result: {expression} = {result}"
    except Exception as e:
        return f"Error calculating '{expression}': {str(e)}"

# Available tools for GPT-OSS
AVAILABLE_TOOLS = {
    "some_fcn": {
        "function": some_fcn,
        "description": "Example tool that prints a message",
        "parameters": {
            "type": "object",
            "properties": {
                "msg": {
                    "type": "string",
                    "description": "Message to print"
                }
            },
            "required": ["msg"]
        }
    },
    "get_weather": {
        "function": get_weather,
        "description": "Get weather information for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Location to get weather for"
                }
            },
            "required": ["location"]
        }
    },
    "calculate": {
        "function": calculate,
        "description": "Calculate a mathematical expression",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to calculate"
                }
            },
            "required": ["expression"]
        }
    }
}

def execute_tool(tool_name, arguments):
    """Execute a tool with given arguments"""
    if tool_name not in AVAILABLE_TOOLS:
        return f"Error: Unknown tool '{tool_name}'"
    
    try:
        tool_func = AVAILABLE_TOOLS[tool_name]["function"]
        result = tool_func(**arguments)
        return result
    except Exception as e:
        return f"Error executing tool '{tool_name}': {str(e)}"

def get_tools_for_gpt():
    """Get tools formatted for GPT-OSS API"""
    tools = []
    for name, tool_info in AVAILABLE_TOOLS.items():
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool_info["description"],
                "parameters": tool_info["parameters"]
            }
        })
    return tools

def chat_with_gpt_oss(messages, model="gpt-oss:20b", api_url="http://localhost:11434/api/chat"):
    """Send messages to GPT-OSS with tools support and return the response"""
    try:
        tools = get_tools_for_gpt()
        
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False
        }
        
        response = requests.post(api_url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            message = result.get("message", {})
            
            # Check if GPT wants to use tools
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                # Execute tools
                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    tool_args = tool_call["function"].get("arguments", {})
                    
                    # Parse arguments if they're a JSON string
                    if isinstance(tool_args, str):
                        try:
                            tool_args = json.loads(tool_args)
                        except json.JSONDecodeError:
                            pass
                    
                    print(f"🔧 Executing tool: {tool_name}({tool_args})")
                    result = execute_tool(tool_name, tool_args)
                    tool_results.append(result)
                
                # Add tool results to conversation
                for i, (tool_call, result) in enumerate(zip(tool_calls, tool_results)):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": f"call_{i}",
                        "name": tool_call["function"]["name"],
                        "content": result
                    })
                
                # Get follow-up response from GPT
                follow_up_payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False
                }
                
                follow_up_response = requests.post(api_url, json=follow_up_payload, timeout=30)
                if follow_up_response.status_code == 200:
                    follow_up_result = follow_up_response.json()
                    return follow_up_result.get("message", {}).get("content", "No response")
                else:
                    return f"Tool execution completed. Results: {'; '.join(tool_results)}"
            else:
                # Regular response without tools
                return message.get("content", "No response")
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except requests.exceptions.RequestException as e:
        return f"Connection error: {e}"
    except Exception as e:
        return f"Error: {e}"

def main():
    print("🤖 GPT-OSS Chat with Tools")
    print("=" * 40)
    print("Available tools:")
    for name, tool_info in AVAILABLE_TOOLS.items():
        print(f"  • {name}: {tool_info['description']}")
    print("\nType 'quit' to exit, 'clear' to clear history")
    print("=" * 40)
    
    # Check if Ollama is running
    try:
        requests.get("http://localhost:11434/api/tags", timeout=5)
    except:
        print("❌ Error: Cannot connect to Ollama")
        print("Please start Ollama first: ollama serve")
        sys.exit(1)
    
    # Initialize conversation history
    conversation_history = []
    
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("🤖 Goodbye!")
                break
            
            if user_input.lower() == 'clear':
                conversation_history = []
                print("🧹 Conversation history cleared!")
                continue
            
            if not user_input:
                continue
            
            # Add user message to history
            conversation_history.append({"role": "user", "content": user_input})
            
            print("🤖 Assistant: ", end="", flush=True)
            response = chat_with_gpt_oss(conversation_history)
            print(response)
            
            # Add assistant response to history
            conversation_history.append({"role": "assistant", "content": response})
            
        except KeyboardInterrupt:
            print("\n🤖 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
