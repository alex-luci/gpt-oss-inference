#!/usr/bin/env python3
import requests
import json
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue

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

class GPTOSSChatBot:
    def __init__(self, model="gpt-oss:20b", api_url="http://localhost:11434/api/chat"):
        self.model = model
        self.api_url = api_url
        self.conversation_history = []
    
    def chat_with_gpt_oss(self, messages):
        """Send messages to GPT-OSS with tools support and return the response"""
        try:
            tools = get_tools_for_gpt()
            
            payload = {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "stream": False
            }
            
            response = requests.post(self.api_url, json=payload, timeout=30)
            
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
                        "model": self.model,
                        "messages": messages,
                        "stream": False
                    }
                    
                    follow_up_response = requests.post(self.api_url, json=follow_up_payload, timeout=30)
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

class ChatUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GPT-OSS Chat with Tools")
        self.root.geometry("900x700")
        
        # Dark theme colors
        self.bg_color = "#1e1e1e"  # Dark background
        self.fg_color = "#ffffff"  # White text
        self.accent_color = "#0078d4"  # Blue accent
        self.secondary_bg = "#2d2d30"  # Slightly lighter dark
        self.border_color = "#3e3e42"  # Border color
        self.user_color = "#4fc3f7"  # Light blue for user
        self.assistant_color = "#81c784"  # Light green for assistant
        self.tool_color = "#ffb74d"  # Orange for tools
        
        self.root.configure(bg=self.bg_color)
        
        # Initialize bot
        self.bot = GPTOSSChatBot()
        self.conversation_history = []
        
        # Message queue for thread-safe updates
        self.message_queue = queue.Queue()
        
        # Create UI
        self.create_widgets()
        
        # Check Ollama connection
        self.check_connection()
    
    def create_widgets(self):
        # Main frame
        main_frame = tk.Frame(self.root, bg=self.bg_color, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(main_frame, text="🤖 GPT-OSS Chat with Tools", 
                               font=("Segoe UI", 18, "bold"), 
                               bg=self.bg_color, fg=self.fg_color)
        title_label.pack(pady=(0, 15))
        
        # Chat display frame
        chat_frame = tk.Frame(main_frame, bg=self.bg_color)
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Chat display label
        chat_label = tk.Label(chat_frame, text="Conversation", 
                             font=("Segoe UI", 12, "bold"),
                             bg=self.bg_color, fg=self.fg_color)
        chat_label.pack(anchor="w", pady=(0, 5))
        
        # Chat display
        self.chat_display = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, 
                                                     state=tk.DISABLED, height=22,
                                                     bg=self.secondary_bg, fg=self.fg_color,
                                                     insertbackground=self.fg_color,
                                                     selectbackground=self.accent_color,
                                                     selectforeground=self.fg_color,
                                                     font=("Consolas", 10),
                                                     relief=tk.FLAT, bd=1,
                                                     highlightthickness=0)
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Configure text tags for styling
        self.chat_display.tag_configure("user", foreground=self.user_color, font=("Consolas", 10, "bold"))
        self.chat_display.tag_configure("assistant", foreground=self.assistant_color, font=("Consolas", 10, "bold"))
        self.chat_display.tag_configure("tool", foreground=self.tool_color, font=("Consolas", 9, "italic"))
        
        # Input frame
        input_frame = tk.Frame(main_frame, bg=self.bg_color)
        input_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Message input
        self.message_entry = tk.Entry(input_frame, font=("Consolas", 11),
                                     bg=self.secondary_bg, fg=self.fg_color,
                                     insertbackground=self.fg_color,
                                     relief=tk.FLAT, bd=1,
                                     highlightthickness=0)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.message_entry.bind("<Return>", self.send_message)
        
        # Send button
        send_button = tk.Button(input_frame, text="Send", command=self.send_message,
                               bg=self.secondary_bg, fg=self.fg_color,
                               font=("Segoe UI", 10),
                               relief=tk.FLAT, bd=1,
                               activebackground=self.accent_color,
                               activeforeground=self.fg_color)
        send_button.pack(side=tk.RIGHT)
        
        # Control buttons frame
        control_frame = tk.Frame(main_frame, bg=self.bg_color)
        control_frame.pack(fill=tk.X)
        
        # Clear button
        clear_button = tk.Button(control_frame, text="Clear Chat", command=self.clear_chat,
                                bg=self.secondary_bg, fg=self.fg_color,
                                font=("Segoe UI", 10),
                                relief=tk.FLAT, bd=1,
                                activebackground=self.accent_color,
                                activeforeground=self.fg_color)
        clear_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Tools info button
        tools_button = tk.Button(control_frame, text="Show Tools", command=self.show_tools,
                                bg=self.secondary_bg, fg=self.fg_color,
                                font=("Segoe UI", 10),
                                relief=tk.FLAT, bd=1,
                                activebackground=self.accent_color,
                                activeforeground=self.fg_color)
        tools_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Status label
        self.status_label = tk.Label(control_frame, text="Ready", 
                                    fg="#4caf50", bg=self.bg_color,
                                    font=("Segoe UI", 10))
        self.status_label.pack(side=tk.RIGHT, padx=(20, 0))
        
        # Focus on message entry
        self.message_entry.focus()
    
    def check_connection(self):
        """Check if Ollama is running"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                self.status_label.config(text="Connected to Ollama", fg="#4caf50")
            else:
                self.status_label.config(text="Ollama error", fg="#f44336")
        except:
            self.status_label.config(text="Cannot connect to Ollama", fg="#f44336")
            messagebox.showerror("Connection Error", 
                               "Cannot connect to Ollama.\nPlease start Ollama first: ollama serve")
    
    def add_message(self, message, sender="assistant"):
        """Add a message to the chat display"""
        self.chat_display.config(state=tk.NORMAL)
        
        if sender == "user":
            self.chat_display.insert(tk.END, "👤 You: ", "user")
            self.chat_display.insert(tk.END, f"{message}\n\n")
        elif sender == "tool":
            self.chat_display.insert(tk.END, "🔧 Tool: ", "tool")
            self.chat_display.insert(tk.END, f"{message}\n\n")
        else:  # assistant
            self.chat_display.insert(tk.END, "🤖 Assistant: ", "assistant")
            self.chat_display.insert(tk.END, f"{message}\n\n")
        
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
    def send_message(self, event=None):
        """Send a message to GPT-OSS"""
        message = self.message_entry.get().strip()
        if not message:
            return
        
        # Clear input
        self.message_entry.delete(0, tk.END)
        
        # Add user message to display
        self.add_message(message, "user")
        
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": message})
        
        # Update status
        self.status_label.config(text="Thinking...", fg="#ff9800")
        
        # Send to GPT-OSS in a separate thread
        thread = threading.Thread(target=self.get_response, daemon=True)
        thread.start()
    
    def get_response(self):
        """Get response from GPT-OSS (runs in separate thread)"""
        try:
            response = self.bot.chat_with_gpt_oss(self.conversation_history)
            
            # Add response to conversation history
            self.conversation_history.append({"role": "assistant", "content": response})
            
            # Queue the response for UI update
            self.message_queue.put(("assistant", response))
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.message_queue.put(("assistant", error_msg))
    
    def update_ui(self):
        """Update UI from message queue (runs in main thread)"""
        try:
            while True:
                sender, message = self.message_queue.get_nowait()
                self.add_message(message, sender)
        except queue.Empty:
            pass
        
        # Update status
        self.status_label.config(text="Ready", fg="#4caf50")
        
        # Schedule next update
        self.root.after(100, self.update_ui)
    
    def clear_chat(self):
        """Clear the chat display and history"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self.conversation_history = []
        self.status_label.config(text="Chat cleared", fg="#2196f3")
    
    def show_tools(self):
        """Show available tools in a popup window"""
        tools_window = tk.Toplevel(self.root)
        tools_window.title("Available Tools")
        tools_window.geometry("600x500")
        tools_window.configure(bg=self.bg_color)
        
        # Create scrolled text widget with dark theme
        tools_text = scrolledtext.ScrolledText(tools_window, wrap=tk.WORD, padx=15, pady=15,
                                             bg=self.secondary_bg, fg=self.fg_color,
                                             insertbackground=self.fg_color,
                                             selectbackground=self.accent_color,
                                             selectforeground=self.fg_color,
                                             font=("Consolas", 10),
                                             relief=tk.FLAT, bd=0)
        tools_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add tools information
        tools_text.insert(tk.END, "Available Tools:\n\n", "title")
        tools_text.tag_configure("title", font=("Consolas", 14, "bold"), foreground=self.accent_color)
        
        for name, tool_info in AVAILABLE_TOOLS.items():
            tools_text.insert(tk.END, f"• {name}\n", "tool_name")
            tools_text.insert(tk.END, f"  {tool_info['description']}\n\n", "tool_desc")
        
        tools_text.tag_configure("tool_name", font=("Consolas", 11, "bold"), foreground=self.user_color)
        tools_text.tag_configure("tool_desc", font=("Consolas", 10), foreground=self.fg_color)
        
        tools_text.config(state=tk.DISABLED)

def main():
    # Check if running in terminal mode
    if len(sys.argv) > 1 and sys.argv[1] == "--terminal":
        # Terminal mode
        print("🤖 GPT-OSS Chat with Tools (Terminal Mode)")
        print("=" * 50)
        print("Available tools:")
        for name, tool_info in AVAILABLE_TOOLS.items():
            print(f"  • {name}: {tool_info['description']}")
        print("\nType 'quit' to exit, 'clear' to clear history")
        print("=" * 50)
        
        # Check if Ollama is running
        try:
            requests.get("http://localhost:11434/api/tags", timeout=5)
        except:
            print("❌ Error: Cannot connect to Ollama")
            print("Please start Ollama first: ollama serve")
            sys.exit(1)
        
        # Initialize bot
        bot = GPTOSSChatBot()
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
                response = bot.chat_with_gpt_oss(conversation_history)
                print(response)
                
                # Add assistant response to history
                conversation_history.append({"role": "assistant", "content": response})
                
            except KeyboardInterrupt:
                print("\n🤖 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    else:
        # GUI mode
        root = tk.Tk()
        app = ChatUI(root)
        
        # Start UI update loop
        app.update_ui()
        
        root.mainloop()

if __name__ == "__main__":
    main()
