#!/usr/bin/env python3
"""
Autonomous GPT-OSS Kitchen Robot Assistant
==========================================
A complete chat interface where GPT-OSS acts as both planner and executor,
making autonomous decisions and controlling a physical robot.
"""

import json
import socket
import requests
import time
from typing import Dict, Any, List, Optional

def send(cmd):
    """Send command to the kitchen robot"""
    try:
        s = socket.socket()
        s.connect(("localhost", 6666))
        s.send(json.dumps(cmd).encode("utf-8"))
        resp = s.recv(65536).decode("utf-8")
        s.close()
        return resp
    except Exception as e:
        return f"Robot connection error: {e}"

class AutonomousGPTOSSBot:
    def __init__(self):
        self.gpt_oss_url = "http://localhost:11434/api/chat"
        self.conversation_history = []
        self.available_functions = {
            "execute_robot_command": self.execute_robot_command,
            "get_robot_status": self.get_robot_status,
            "wait_seconds": self.wait_seconds
        }
        
        # Initialize with enhanced system prompt
        self.conversation_history = [{
            "role": "system",
            "content": self._get_system_prompt()
        }]
        
        print("🤖 Autonomous GPT-OSS Kitchen Assistant initialized!")
    
    def _get_system_prompt(self):
        return """You are an autonomous kitchen robot assistant with full decision-making and execution capabilities. You can both plan complex tasks and directly control a physical robot.

## Your Dual Role:
1. **Task Planner**: Break down complex requests into step-by-step actions
2. **Robot Controller**: Execute each action using function calls

## Available Functions:
- execute_robot_command(language_instruction: str, actions_to_execute: int = 50): Execute robot actions
- get_robot_status(): Check current robot status
- wait_seconds(seconds: int): Wait for a specified number of seconds

## Available Robot Actions:
- "Open the left cabinet door"
- "Close the left cabinet door"
- "Take off the lid from the pot"
- "Put the lid back on the pot"
- "Pick up the pineapple from the cabinet and place it in the pot"
- "Add salt to the pot"

## Physical Constraints (You Must Enforce):
- Cannot access pineapple unless cabinet door is open
- Cannot put pineapple in pot if lid is on pot
- Cannot add salt if lid is on pot
- Must close cabinet door after removing items (safety)
- Must put lid back on pot at the end

## Your Process:
1. **Analyze** the user's request and current situation
2. **Plan** the sequence of actions needed
3. **Execute** each action step-by-step using function calls
4. **Verify** completion and provide status updates
5. **Handle** any errors or unexpected situations

## Decision Making Examples:

**User**: "Make a pineapple smoothie"
**Your Response**: "I'll help you make a pineapple smoothie! Let me break this down:
1. First, I need to open the cabinet to access the pineapple
2. Then remove the pot lid so I can add ingredients
3. Get the pineapple and put it in the pot
4. Close the cabinet for safety
5. Put the lid back on

Let me start by opening the cabinet door."
*[Then call execute_robot_command function]*

**User**: "What's happening?"
**Your Response**: "Let me check the robot status for you."
*[Then call get_robot_status function]*

## Key Behaviors:
- **Be proactive**: If a task requires multiple steps, plan and execute them all
- **Be safe**: Always follow physical constraints
- **Be communicative**: Explain your plan before executing
- **Be adaptive**: If something fails, replan and try alternative approaches
- **Be thorough**: Complete entire tasks, not just single actions
- **Use wait_seconds()** if you need to pause between actions

You have full autonomy to decide when and how to use functions. Take initiative and complete tasks end-to-end!"""

    def execute_robot_command(self, language_instruction: str, actions_to_execute: int = 50):
        """Execute a command on the robot"""
        cmd = {
            "command": "execute_task",
            "language_instruction": language_instruction,
            "actions_to_execute": actions_to_execute
        }
        
        print(f"🤖 Robot executing: {language_instruction}")
        result = send(cmd)
        
        return {
            "status": "success" if "error" not in result.lower() else "error",
            "result": result,
            "instruction": language_instruction,
            "timestamp": time.time()
        }
    
    def get_robot_status(self):
        """Get current robot status"""
        cmd = {"command": "get_status"}
        print("🔍 Checking robot status...")
        result = send(cmd)
        
        return {
            "status": "success" if "error" not in result.lower() else "error",
            "robot_status": result,
            "timestamp": time.time()
        }
    
    def wait_seconds(self, seconds: int):
        """Wait for specified seconds"""
        print(f"⏳ Waiting {seconds} seconds...")
        time.sleep(seconds)
        return {
            "status": "success",
            "message": f"Waited {seconds} seconds",
            "timestamp": time.time()
        }
    
    def chat(self, user_message: str) -> str:
        """Enhanced chat that lets GPT-OSS make all decisions"""
        print(f"\n👤 You: {user_message}")
        print("─" * 50)
        
        # Add user message
        self.conversation_history.append({
            "role": "user", 
            "content": user_message
        })
        
        # Let GPT-OSS decide what to do (may involve multiple function calls)
        return self._autonomous_execution()
    
    def _autonomous_execution(self) -> str:
        """Let GPT-OSS autonomously decide and execute functions"""
        max_iterations = 15  # Prevent infinite loops
        iteration = 0
        final_response = ""
        
        while iteration < max_iterations:
            iteration += 1
            print(f"\n🧠 GPT-OSS Decision Cycle {iteration}")
            
            # Get GPT-OSS response
            response_data = self._call_gpt_oss_with_tools()
            
            if not response_data:
                return "I encountered an error. Please try again."
            
            message = response_data.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            
            # Display GPT-OSS's reasoning/plan
            if content:
                print(f"💭 GPT-OSS: {content}")
                final_response = content
            
            # Execute any function calls GPT-OSS decided to make
            if tool_calls:
                print(f"🔧 GPT-OSS decided to execute {len(tool_calls)} action(s)")
                
                # Add assistant message to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls
                })
                
                # Execute each tool call
                for i, tool_call in enumerate(tool_calls):
                    function_name = tool_call["function"]["name"]
                    function_args = tool_call["function"]["arguments"]
                    
                    print(f"⚡ Executing: {function_name}({function_args})")
                    
                    if function_name in self.available_functions:
                        try:
                            result = self.available_functions[function_name](**function_args)
                            print(f"✅ Result: {result}")
                            
                            # Add tool result to conversation
                            self.conversation_history.append({
                                "role": "tool",
                                "tool_call_id": f"call_{i}",
                                "name": function_name,
                                "content": json.dumps(result)
                            })
                            
                        except Exception as e:
                            error_result = {"status": "error", "error": str(e)}
                            print(f"❌ Error: {e}")
                            
                            self.conversation_history.append({
                                "role": "tool",
                                "tool_call_id": f"call_{i}",
                                "name": function_name,
                                "content": json.dumps(error_result)
                            })
                
                # Continue the loop - let GPT-OSS decide what to do next
                continue
            
            else:
                # No more function calls, GPT-OSS is done
                if content:
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": content
                    })
                    print(f"🎯 Task completed!")
                    return content
                else:
                    print(f"🎯 Task completed!")
                    return final_response or "Task completed!"
        
        print(f"⚠️  Reached maximum decision cycles ({max_iterations})")
        return final_response or "I completed the maximum number of decision cycles. The task should be done!"
    
    def _call_gpt_oss_with_tools(self) -> Optional[Dict]:
        """Call GPT-OSS with function calling enabled"""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "execute_robot_command",
                    "description": "Execute a command on the kitchen robot",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "language_instruction": {
                                "type": "string",
                                "description": "Natural language instruction for the robot"
                            },
                            "actions_to_execute": {
                                "type": "integer",
                                "description": "Number of actions to execute (default: 50)",
                                "default": 50
                            }
                        },
                        "required": ["language_instruction"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_robot_status",
                    "description": "Get the current status of the robot",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "wait_seconds",
                    "description": "Wait for a specified number of seconds",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "seconds": {
                                "type": "integer",
                                "description": "Number of seconds to wait"
                            }
                        },
                        "required": ["seconds"]
                    }
                }
            }
        ]
        
        payload = {
            "model": "gpt-oss:20b",
            "messages": self.conversation_history,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False
        }
        
        try:
            response = requests.post(self.gpt_oss_url, json=payload, timeout=45)
            if response.status_code == 200:
                return self._parse_gpt_response(response.text)
            else:
                print(f"❌ HTTP Error: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.Timeout:
            print("❌ GPT-OSS request timed out")
            return None
        except Exception as e:
            print(f"❌ Error calling GPT-OSS: {e}")
            return None
    
    def _parse_gpt_response(self, response_text: str) -> Optional[Dict]:
        """Parse GPT-OSS response"""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            print(f"Raw response: {response_text[:200]}...")
            return None
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation"""
        user_messages = [msg for msg in self.conversation_history if msg["role"] == "user"]
        assistant_messages = [msg for msg in self.conversation_history if msg["role"] == "assistant"]
        tool_calls = sum(1 for msg in self.conversation_history if msg["role"] == "tool")
        
        return f"""
📊 Conversation Summary:
• User messages: {len(user_messages)}
• Assistant responses: {len(assistant_messages)}
• Function calls executed: {tool_calls}
• Total conversation length: {len(self.conversation_history)} messages
"""

def test_robot_connection():
    """Test if robot is available"""
    print("🧪 Testing robot connection...")
    try:
        test_cmd = {"command": "get_status"}
        result = send(test_cmd)
        print(f"✅ Robot connection successful: {result}")
        return True
    except Exception as e:
        print(f"❌ Robot connection failed: {e}")
        print("Make sure your robot is running on localhost:6666")
        return False

def test_gpt_oss_connection():
    """Test if GPT-OSS is available"""
    print("🧪 Testing GPT-OSS connection...")
    try:
        payload = {
            "model": "gpt-oss:20b",
            "messages": [{"role": "user", "content": "Hello, just say 'Hi' back"}],
            "stream": False
        }
        response = requests.post("http://localhost:11434/api/chat", json=payload, timeout=10)
        if response.status_code == 200:
            result = json.loads(response.text)
            content = result.get("message", {}).get("content", "")
            print(f"✅ GPT-OSS connection successful: '{content}'")
            return True
        else:
            print(f"❌ GPT-OSS returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ GPT-OSS connection failed: {e}")
        print("Make sure GPT-OSS is running: ollama run gpt-oss:20b")
        return False

def main():
    """Main interactive chat interface"""
    print("🤖 Autonomous GPT-OSS Kitchen Robot Assistant")
    print("=" * 60)
    print("🧠 GPT-OSS will autonomously plan and execute kitchen tasks!")
    print("🤖 Direct robot control with intelligent decision making")
    print("=" * 60)
    
    # Test connections
    print("\n🔧 System Check:")
    gpt_oss_ok = test_gpt_oss_connection()
    robot_ok = test_robot_connection()
    
    if not gpt_oss_ok:
        print("\n❌ Cannot connect to GPT-OSS. Please start it with:")
        print("   ollama run gpt-oss:20b")
        return
    
    if not robot_ok:
        print("\n⚠️  Robot not available, but you can still test the chat interface")
        print("(Robot commands will show connection errors)")
    
    print("\n✅ System ready!")
    print("\n📋 What you can ask:")
    print("• 'Make a pineapple smoothie' - Full autonomous task execution")
    print("• 'Open the cabinet and get the pineapple' - Multi-step actions")
    print("• 'What's the robot status?' - Status checks")
    print("• 'Clean up the kitchen' - Complex task planning")
    print("• 'Help me cook dinner' - Creative task interpretation")
    print("\n💡 GPT-OSS will autonomously break down tasks and execute them!")
    print("Type 'quit', 'summary', or 'help' for special commands")