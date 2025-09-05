import json
import socket
import requests
import re
from typing import Dict, Any, Optional

def send(cmd):
    """Function that GPT-OSS will call"""
    s = socket.socket()
    s.connect(("localhost", 6666))
    s.send(json.dumps(cmd).encode("utf-8"))
    resp = s.recv(65536).decode("utf-8")
    s.close()
    return resp

class GPTOSSFunctionCaller:
    def __init__(self):
        self.gpt_oss_url = "http://localhost:11434/api/chat"
        self.available_functions = {
            "execute_robot_command": self.execute_robot_command,
            "get_robot_status": self.get_robot_status
        }
    
    def execute_robot_command(self, language_instruction: str, actions_to_execute: int = 120):
        """Function that GPT-OSS can call to control the robot"""
        cmd = {
            "command": "execute_task",
            "language_instruction": language_instruction,
            "actions_to_execute": actions_to_execute
        }
        
        try:
            result = send(cmd)
            return {
                "status": "success",
                "result": result,
                "command_sent": cmd
            }
        except Exception as e:
            return {
                "status": "error", 
                "error": str(e),
                "command_sent": cmd
            }
    
    def get_robot_status(self):
        """Get current robot status"""
        cmd = {"command": "get_status"}
        try:
            result = send(cmd)
            return {"status": "success", "robot_status": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _parse_gpt_response(self, response_text: str) -> Optional[Dict]:
        """Safely parse GPT-OSS response that might have malformed JSON"""
        try:
            # Try parsing as single JSON
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract the first valid JSON object
            try:
                # Find the first complete JSON object
                json_start = response_text.find('{')
                if json_start == -1:
                    return None
                
                brace_count = 0
                json_end = json_start
                
                for i, char in enumerate(response_text[json_start:], json_start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
                
            except (json.JSONDecodeError, ValueError) as e:
                print(f"❌ Failed to parse GPT response: {e}")
                print(f"Raw response: {response_text[:200]}...")
                return None
    
    def chat_with_functions(self, user_message: str):
        """Chat with GPT-OSS that can call functions"""
        
        # Simplified approach - let's try without function calling first
        system_prompt = """You are a kitchen assistant that can directly control a robot. 

When you need to control the robot, respond with EXACTLY this format:
FUNCTION_CALL: execute_robot_command
ARGS: {"language_instruction": "your instruction here", "actions_to_execute": 120}

Available instructions:
- "Open the left cabinet door"
- "Close the left cabinet door" 
- "Take off the lid from the pot"
- "Put the lid back on the pot"
- "Pick up the pineapple from the cabinet and place it in the pot"
- "Add salt to the pot"

Example response:
FUNCTION_CALL: execute_robot_command
ARGS: {"language_instruction": "Open the left cabinet door", "actions_to_execute": 120}

You can also provide explanations before or after the function call."""

        # Simple payload without tools
        payload = {
            "model": "gpt-oss:20b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": False
        }
        
        try:
            # Call GPT-OSS
            response = requests.post(self.gpt_oss_url, json=payload, timeout=30)
            response.raise_for_status()
            
            # Get raw response text
            response_text = response.text
            print(f"🔍 Raw GPT-OSS response: {response_text[:300]}...")
            
            # Try to parse JSON
            result = self._parse_gpt_response(response_text)
            if not result:
                print("❌ Could not parse JSON, treating as text response")
                return {"message": response_text, "function_calls": []}
            
            # Extract message content
            message_content = result.get("message", {}).get("content", "")
            print(f"📝 GPT-OSS says: {message_content}")
            
            # Check for function calls in the text
            if "FUNCTION_CALL:" in message_content:
                return self._handle_text_function_calls(message_content, user_message)
            else:
                return {"message": message_content, "function_calls": []}
                
        except requests.exceptions.Timeout:
            return {"error": "GPT-OSS request timed out"}
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {e}"}
        except Exception as e:
            return {"error": f"Unexpected error: {e}"}
    
    def _handle_text_function_calls(self, message_content: str, original_message: str):
        """Parse and execute function calls from text response"""
        results = []
    
        # Parse function calls from text
        lines = message_content.split('\n')
        i = 0
    
        while i < len(lines):
            line = lines[i].strip()
        
            if line.startswith("FUNCTION_CALL:"):
                function_name = line.replace("FUNCTION_CALL:", "").strip()
            
                # Look for ARGS on next line
                if i + 1 < len(lines) and lines[i + 1].strip().startswith("ARGS:"):
                    args_line = lines[i + 1].strip().replace("ARGS:", "").strip()
                
                    try:
                        function_args = json.loads(args_line)
                        print(f"🤖 GPT-OSS is calling: {function_name}({function_args})")
                    
                        # ✅ THIS IS THE FIX - Actually execute the function
                        if function_name in self.available_functions:
                            try:
                                # Call the actual function method
                                function_method = self.available_functions[function_name]
                                result = function_method(**function_args)  # This executes the function!
                            
                                results.append({
                                    "function": function_name,
                                    "args": function_args,
                                    "result": result
                                })
                                print(f"✅ Function executed! Result: {result}")
                            
                            except Exception as e:
                                error_result = {"status": "error", "error": str(e)}
                                results.append({
                                    "function": function_name,
                                    "args": function_args,
                                    "result": error_result
                                })
                                print(f"❌ Function execution error: {e}")
                        else:
                            print(f"❌ Unknown function: {function_name}")
                            results.append({
                                "function": function_name,
                                "args": function_args,
                                "result": {"status": "error", "error": f"Unknown function: {function_name}"}
                            })
                        
                    except json.JSONDecodeError as e:
                        print(f"❌ Could not parse function arguments: {args_line}")
                        print(f"Error: {e}")
            
                i += 2  # Skip both FUNCTION_CALL and ARGS lines
            else:
                i += 1
    
        return results  # Return the results so they can be used

# Test with better error handling
if __name__ == "__main__":
    assistant = GPTOSSFunctionCaller()
    
    try:
        print("🚀 Testing GPT-OSS function calling...")
        response = assistant.chat_with_functions("Open the cabinet door")
        print("✅ Final Response:", json.dumps(response, indent=2))
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
