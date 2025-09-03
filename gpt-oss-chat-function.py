import json
import socket
import requests
from typing import Dict, Any, List

def send(cmd):
    """Function that GPT-OSS will call"""
    s = socket.socket()
    s.connect(("localhost", 7000))
    s.send(json.dumps(cmd).encode("utf-8"))
    resp = s.recv(65536).decode("utf-8")
    s.close()
    return resp

class GPTOSSChatBot:
    def __init__(self):
        self.gpt_oss_url = "http://localhost:11434/api/chat"
        self.conversation_history = []
        self.available_functions = {
            "execute_robot_command": self.execute_robot_command,
            "get_robot_status": self.get_robot_status
        }
        
        # Initialize with system prompt that enables function calling
        self.conversation_history = [{
            "role": "system",
            "content": self._get_system_prompt()
        }]
    
    def _get_system_prompt(self):
        return """You are a kitchen assistant helping to make a pineapple smoothie. You must follow the physical constraints of the kitchen and use actions in the correct sequence.

## Kitchen Layout
- **Left**: Cabinet (currently closed) containing a pineapple
- **Center**: Pot with lid on top
- **Right**: Salt shaker

## Available Functions & Actions
You can execute these robot actions using the execute_robot_command function:
- "Open the left cabinet door"
- "Close the left cabinet door"
- "Take off the lid from the gray recipient and place it on the counter"
- "Pick up the lid from the counter and put it on the gray recipient"
- "Pick up the green pineapple from the left cabinet and place it in the gray recipient"
- "Add salt to the pot"

## Physical Constraints
1. Cannot access pineapple unless cabinet door is open
2. Cannot put pineapple in pot if lid is on the pot
3. Cannot add salt if lid is on the pot
4. Must close cabinet door after removing items (kitchen safety)
5. Must put lid back on pot at the end
6. **Salt rule**: Only add salt if the user explicitly requests it - do not add salt unless told to do so

## Your Process
1. **Analyze** the current kitchen state and user request
2. **Plan** the sequence of actions needed following physical constraints
3. **Execute** each action using the execute_robot_command function
4. **Verify** completion and provide status updates
5. **Handle** any errors and replan if necessary

## Decision Making Examples

**User**: "Make a pineapple smoothie"
**Your Response**: "I'll help you make a pineapple smoothie! Let me break this down:
1. First, I need to open the cabinet to access the pineapple
2. Then remove the pot lid so I can add ingredients
3. Get the pineapple and put it in the pot
4. Close the cabinet for safety
5. Put the lid back on

Let me start by opening the cabinet door."
*[Then call execute_robot_command with "Open the left cabinet door"]*

**User**: "What's happening?"
**Your Response**: "Let me check the robot status for you."
*[Then call get_robot_status function]*

## Key Behaviors
- **Be proactive**: If a task requires multiple steps, plan and execute them all
- **Be safe**: Always follow physical constraints
- **Be communicative**: Explain your plan before executing
- **Be adaptive**: If something fails, replan and try alternative approaches
- **Be thorough**: Complete entire tasks, not just single actions
- **Execute step-by-step**: Use execute_robot_command for each physical action needed

## Function Usage
- Use execute_robot_command(language_instruction, actions_to_execute=150, use_angle_stop=True) for robot actions
- Use get_robot_status() to check robot status when needed
- Always explain what you're doing before calling functions
- Wait for function results before planning next steps

Remember: The final state should have the cabinet door closed and the lid back on the pot. Take initiative and complete tasks end-to-end using the available functions!"""

    def execute_robot_command(self, language_instruction: str, actions_to_execute: int = 150, use_angle_stop: bool = True):
        """Execute a command on the robot"""
        cmd = {
            "command": "execute_task",
            "language_instruction": language_instruction,
            "actions_to_execute": actions_to_execute,
            "use_angle_stop": True
        }
        
        try:
            result = send(cmd)
            return {
                "status": "success",
                "result": result,
                "instruction": language_instruction,
                "use_angle_stop": True
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "instruction": language_instruction,
                "use_angle_stop": True
            }
    
    def get_robot_status(self):
        """Get current robot status"""
        cmd = {"command": "get_status"}
        try:
            result = send(cmd)
            return {"status": "success", "robot_status": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def chat(self, user_message: str) -> str:
        """Main chat function - handles user input and returns response"""
        # print(f"👤 You: {user_message}")
        
        # Add user message to conversation
        self.conversation_history.append({
            "role": "user", 
            "content": user_message
        })
        
        # Get GPT-OSS response
        gpt_response = self._call_gpt_oss()
        
        return gpt_response
    
    def _call_gpt_oss(self) -> str:
        """Call GPT-OSS API with function calling support"""
        
        # Define available tools for GPT-OSS
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
                                "description": "Number of actions to execute (default: 150)",
                                "default": 150
                            },
                            "use_angle_stop": {
                                "type": "boolean",
                                "description": "Whether to use angle stop (default: true)",
                                "default": True
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
            print(f"🔍 Calling GPT-OSS with tools enabled...")
            
            response = requests.post(self.gpt_oss_url, json=payload, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ HTTP Error: {response.status_code}")
                return f"HTTP Error {response.status_code}: {response.text}"
            
            result = self._parse_gpt_response(response.text)
            message = result.get("message", {})
            
            # Get the text content
            content = message.get("content", "")
            
            # Check for tool calls
            tool_calls = message.get("tool_calls", [])
            
            if tool_calls:
                print(f"🔧 GPT-OSS wants to call {len(tool_calls)} function(s)")
                
                # Execute tool calls
                tool_results = []
                for tool_call in tool_calls:
                    function_name = tool_call["function"]["name"]
                    function_args = tool_call["function"]["arguments"]
                    
                    print(f"🤖 Calling: {function_name}({function_args})")
                    
                    if function_name in self.available_functions:
                        try:
                            result = self.available_functions[function_name](**function_args)
                            tool_results.append(result)
                            print(f"✅ Function result: {result}")
                        except Exception as e:
                            error_result = {"status": "error", "error": str(e)}
                            tool_results.append(error_result)
                            print(f"❌ Function error: {e}")
                    else:
                        print(f"❌ Unknown function: {function_name}")
                
                # Add assistant message with tool calls to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls
                })
                
                # Add tool results to history
                for i, (tool_call, result) in enumerate(zip(tool_calls, tool_results)):
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": f"call_{i}",
                        "name": tool_call["function"]["name"],
                        "content": json.dumps(result)
                    })
                
                # Get follow-up response from GPT-OSS
                follow_up_payload = {
                    "model": "gpt-oss:20b",
                    "messages": self.conversation_history,
                    "stream": False
                }
                
                follow_up_response = requests.post(self.gpt_oss_url, json=follow_up_payload, timeout=30)
                follow_up_result = self._parse_gpt_response(follow_up_response.text)
                follow_up_content = follow_up_result.get("message", {}).get("content", "")
                
                if follow_up_content:
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": follow_up_content
                    })
                    print(f"🤖 Assistant: {follow_up_content}")
                    return follow_up_content
                else:
                    # Just return a summary if no follow-up
                    summary = f"I executed {len(tool_results)} action(s) for you!"
                    print(f"🤖 Assistant: {summary}")
                    return summary
            
            else:
                # No tool calls, just regular response
                if content:
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": content
                    })
                    print(f"🤖 Assistant: {content}")
                    return content
                else:
                    print("❌ No content or tool calls in response")
                    return "I didn't understand that. Can you try again?"
            
        except Exception as e:
            error_msg = f"Error calling GPT-OSS: {e}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def _parse_gpt_response(self, response_text: str) -> Dict:
        """Parse GPT-OSS response"""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            return {"message": {"content": response_text}}

# Interactive Chat Interface
def main():
    print("🤖 Kitchen Robot Assistant Chat (with Function Calling)")
    print("=" * 60)
    print("✅ Using GPT-OSS native function calling!")
    print("\nYou can ask me to:")
    print("• Open/close cabinet doors")
    print("• Remove/replace pot lids") 
    print("• Move pineapples and add salt")
    print("• Check robot status")
    print("• Or just chat!")
    print("\nType 'quit' to exit")
    print("=" * 60)
    
    bot = GPTOSSChatBot()
    
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("🤖 Assistant: Goodbye! It was nice helping you in the kitchen!")
                break
            
            if not user_input:
                continue
            
            # Get bot response (this handles function calls automatically)
            bot.chat(user_input)
            
        except KeyboardInterrupt:
            print("\n🤖 Assistant: Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()