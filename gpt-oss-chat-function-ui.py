import json
import socket
import requests
from typing import Dict, Any, List, Callable, Optional
import threading
import queue
import time
from datetime import datetime, timezone
# removed tkinter; switch to PyQt5
from PyQt5 import QtWidgets, QtCore

# ----- Logging helpers -----
VERBOSE_LOGS = False
ACTIVITY_LOG_HOOK: Optional[Callable[[str], None]] = None

def _log_debug(message: str):
    if VERBOSE_LOGS:
        print(message)
        if ACTIVITY_LOG_HOOK:
            try:
                ACTIVITY_LOG_HOOK(message)
            except Exception:
                pass

def _log_info(message: str):
    print(message)
    if ACTIVITY_LOG_HOOK:
        try:
            ACTIVITY_LOG_HOOK(message)
        except Exception:
            pass


def send(cmd):
    """Function that GPT-OSS will call"""
    # s = socket.socket()
    # s.connect(("localhost", 7000))
    # s.send(json.dumps(cmd).encode("utf-8"))
    # resp = s.recv(65536).decode("utf-8")
    # s.close()
    _log_debug(f"[Robot] send {cmd}")
    # return resp

class GPTOSSChatBot:
    def __init__(self,
                 on_assistant_message: Optional[Callable[[str], None]] = None,
                 on_tool_result: Optional[Callable[[str, Dict[str, Any]], None]] = None,
                 on_status_update: Optional[Callable[[Dict[str, Any]], None]] = None,
                 on_plan_update: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
                 on_execute_start: Optional[Callable[[str], None]] = None,
                 on_assistant_stream: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.gpt_oss_url = "http://localhost:11434/api/chat"
        self.conversation_history = []
        self.available_functions = {
            "execute_robot_command": self.execute_robot_command,
            "get_robot_status": self.get_robot_status,
            "update_kitchen_state": self.update_kitchen_state,
            "mark_task_complete": self.mark_task_complete,
            "get_current_plan": self.get_current_plan,
            "create_plan": self.create_plan,
            "review_plan": self.review_plan
        }
        
        # UI callbacks
        self.on_assistant_message = on_assistant_message
        self.on_tool_result = on_tool_result
        self.on_status_update = on_status_update
        self.on_plan_update = on_plan_update
        self.on_execute_start = on_execute_start
        self.on_assistant_stream = on_assistant_stream
        
        # State tracking
        self.last_robot_status: Optional[Dict[str, Any]] = None
        self.current_task: Optional[str] = None
        self.current_user_task_text: Optional[str] = None
        self.task_list: List[Dict[str, Any]] = []  # [{"id": 1, "title": str, "done": bool}]
        # Initialize with default kitchen state
        self.kitchen_state: Dict[str, Any] = {
            "cabinet_open": False,
            "lid_on_pot": True,
            "pineapple_in_pot": False,
            "salt_added": False
        }
        
        # Initialize with system prompt that enables function calling
        self.conversation_history = [{
            "role": "system",
            "content": self._get_system_prompt()
        }]
    
    def _get_system_prompt(self):
        return """You are a fully autonomous kitchen assistant. You have complete control over task planning, execution, and state management.

## Your Capabilities
You can execute robot actions and manage your own state using these functions:
- execute_robot_command(language_instruction, use_angle_stop=True): Control the robot
- get_robot_status(): Check robot status
- update_kitchen_state(state_updates): Update your understanding of kitchen state
- mark_task_complete(task_id): Mark tasks as complete in your plan
- get_current_plan(): Review your current plan and state
- create_plan(tasks): Create a new task plan for the user
- review_plan(): Ask an independent review to validate or revise your plan before execution

## Canonical Robot Commands (MUST use exact text; DO NOT paraphrase)
- "Open the left cabinet door"
- "Close the left cabinet door"
- "Take off the lid from the gray recipient and place it on the counter"
- "Pick up the lid from the counter and put it on the gray recipient"
- "Pick up the green pineapple from the left cabinet and place it in the gray recipient"
- "Put salt in the gray recipient"

## Your Responsibilities
1. **Plan Creation**: ALWAYS create a plan first using create_plan() when user requests a task
2. **Plan Validation**: AFTER creating a plan, call review_plan() and proceed ONLY if approved. If not approved, revise and re‑review until approved
3. **Autonomous Execution**: Do NOT wait for user confirmation; once the plan is approved, immediately execute it end‑to‑end
4. **State Tracking**: Maintain and update kitchen state as you work
5. **Task Management**: Mark tasks complete as you finish them
6. **Adaptive Execution**: Modify plans based on real conditions
7. **Status Communication**: Keep the user informed of progress (avoid internal tool logs; communicate only meaningful updates)

## Available Robot Actions
- "Open the left cabinet door"
- "Close the left cabinet door"
- "Take off the lid from the gray recipient and place it on the counter"
- "Pick up the lid from the counter and put it on the gray recipient"
- "Pick up the green pineapple from the left cabinet and place it in the gray recipient"
- "Put salt in the gray recipient"

## Physical Constraints
- Cannot access pineapple unless cabinet door is open
- Cannot put pineapple in pot if lid is on pot
- Cannot add salt if lid is on pot
- Must close cabinet door after removing items
- Must put lid back on pot at the end (for smoothie tasks)

## Your Autonomous Process
1. **Analyze** user request and current state
2. **Plan** by creating a task list using create_plan() - THIS IS REQUIRED
3. **Validate** the plan using review_plan(); if not approved, revise and re‑validate
4. **Respect physical constraints**: Do not attempt to do something that is physically impossible
5. **Execute** each step using robot commands
6. **Update** kitchen state after each action
7. **Mark** tasks complete as you finish them
8. **Adapt** if conditions change or actions fail
9. **Communicate** progress and completion

## State Management Examples
After opening cabinet: update_kitchen_state({"cabinet_open": True})
After removing lid: update_kitchen_state({"lid_on_pot": False})
After completing a task: mark_task_complete(task_id)

## Key Behaviors
- **Be autonomous**: Make all decisions yourself
- **Be adaptive**: Change plans based on real conditions
- **Be thorough**: Complete entire tasks end-to-end
- **Be communicative**: Explain what you're doing and why
- **Be state-aware**: Always update your understanding of the kitchen
- **ALWAYS CREATE A PLAN FIRST**: Use create_plan() before executing any tasks
- **VALIDATE THE PLAN**: Use review_plan() and only execute an approved plan
- **USE CANONICAL COMMANDS**: When calling execute_robot_command, the language_instruction MUST be exactly one of the canonical commands above (no paraphrasing)
- **Salt rule**: Only add salt if the user explicitly requests it - do not add salt unless told to do so

You have complete autonomy. Plan, execute, and manage everything yourself!"""

    def execute_robot_command(self, language_instruction: str, use_angle_stop: bool = True):
        """Execute a command on the robot"""
        self.current_task = language_instruction
        # Notify UI execution start
        if self.on_execute_start:
            try:
                self.on_execute_start(language_instruction)
            except Exception:
                pass
        
        cmd = {
            "command": "execute_task",
            "language_instruction": language_instruction,
            "actions_to_execute": 150,
            "use_angle_stop": True
        }
        
        try:
            result = send(cmd)
            payload = {
                "status": "success",
                "result": result,
                "instruction": language_instruction,
                "use_angle_stop": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            if self.on_tool_result:
                self.on_tool_result("execute_robot_command", payload)
            _log_info(f"[Robot] OK execute: {language_instruction}")
            return payload
        except Exception as e:
            payload = {
                "status": "error",
                "error": str(e),
                "instruction": language_instruction,
                "use_angle_stop": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if self.on_tool_result:
                self.on_tool_result("execute_robot_command", payload)
            _log_info(f"[Robot] ERR execute: {language_instruction} -> {e}")
            return payload
    
    def get_robot_status(self):
        """Get current robot status"""
        cmd = {"command": "get_status"}
        try:
            result = send(cmd)
            payload = {"status": "success", "robot_status": result, "timestamp": datetime.now(timezone.utc).isoformat()}
            self.last_robot_status = payload
            if self.on_tool_result:
                self.on_tool_result("get_robot_status", payload)
            if self.on_status_update:
                self.on_status_update(payload)
            _log_info("[Robot] OK status")
            return payload
        except Exception as e:
            payload = {"status": "error", "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
            if self.on_tool_result:
                self.on_tool_result("get_robot_status", payload)
            if self.on_status_update:
                self.on_status_update(payload)
            _log_info(f"[Robot] ERR status -> {e}")
            return payload
    
    def update_kitchen_state(self, state_updates: Dict[str, Any]):
        """Let GPT-OSS update kitchen state dynamically"""
        try:
            if not isinstance(state_updates, dict):
                raise ValueError("state_updates must be an object")
            self.kitchen_state.update(state_updates)
            if self.on_status_update:
                self.on_status_update({
                    "status": "success",
                    "kitchen_state": self.kitchen_state,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            _log_info(f"[State] {state_updates}")
            return {
                "status": "success",
                "updated_state": self.kitchen_state,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def mark_task_complete(self, task_id: int):
        """Let GPT-OSS mark tasks as complete"""
        try:
            for task in self.task_list:
                if task.get("id") == task_id:
                    task["done"] = True
                    break
            if self.on_plan_update:
                self.on_plan_update(self.task_list)
            _log_info(f"[Plan] Task #{task_id} complete")
            return {
                "status": "success",
                "updated_tasks": self.task_list,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_current_plan(self):
        """Let GPT-OSS query current plan"""
        return {
            "status": "success",
            "current_plan": self.task_list,
            "kitchen_state": self.kitchen_state,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def create_plan(self, tasks: List[Dict[str, Any]]):
        """Let GPT-OSS create a new task plan"""
        try:
            if not isinstance(tasks, list):
                raise ValueError("tasks must be a list")
            
            # Extract only task descriptions for the checklist
            formatted_tasks = []
            for i, task in enumerate(tasks):
                if isinstance(task, dict):
                    # Extract description from task object
                    description = task.get("title", task.get("description", str(task)))
                    formatted_tasks.append({
                        "id": i + 1,
                        "title": description,
                        "done": False
                    })
                else:
                    # If task is just a string, use it as description
                    formatted_tasks.append({
                        "id": i + 1,
                        "title": str(task),
                        "done": False
                    })
            
            self.task_list = formatted_tasks
            if self.on_plan_update:
                self.on_plan_update(self.task_list)
            _log_info(f"[Plan] Created {len(self.task_list)} tasks")
            return {
                "status": "success",
                "created_plan": self.task_list,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def review_plan(self, instructions: Optional[str] = None):
        """Ask the model to strictly review the current plan against the current kitchen_state and optionally revise it.
        Returns a payload with approved, reasons, and optionally a revised plan that is applied to the UI.
        """
        try:
            # Build a compact review prompt. No hardcoded rules beyond natural-language rubric.
            rubric = (
                "You are a strict plan validator for a kitchen robot. Review the proposed plan for physical feasibility, safety, and completeness, using the provided kitchen_state. "
                "Only evaluate ordering and preconditions; do NOT change the wording of any robot action. "
                "If the plan is valid, return approved=true. If not, return approved=false and provide a revised plan that fixes issues. "
                "Do NOT paraphrase robot actions: any robot action step MUST use the exact canonical command strings; you may only reorder, insert, or remove canonical steps. "
                "Acceptance criteria for approval (all must hold): (1) Cabinet is opened before any action that takes items from it and remains open until those actions are complete; (2) Lid is removed before any action that requires access to the gray recipient's contents; (3) Lid is restored at the end when appropriate; (4) Cabinet is closed at the end if it was opened; (5) All robot actions are from the canonical command list and wording is unchanged. "
                "Prefer minimal changes, preserve intent, and ensure steps are sequenced so preconditions are met before actions. "
                "Respond ONLY in JSON with keys: approved (boolean), reasons (array of strings), revised_plan (array of step objects with 'title' field) when applicable."
            )
            review_messages = [
                {"role": "system", "content": rubric},
                {"role": "user", "content": json.dumps({
                    "kitchen_state": self.kitchen_state,
                    "plan": self.task_list
                })}
            ]

            payload = {"model": "gpt-oss:20b", "messages": review_messages, "stream": False}
            resp = requests.post(self.gpt_oss_url, json=payload, timeout=60)
            if resp.status_code != 200:
                _log_info(f"[Review] HTTP {resp.status_code}")
                return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text}"}
            parsed = self._parse_gpt_response(resp.text)
            message = parsed.get("message", {})
            content = message.get("content", "").strip()
            try:
                result = json.loads(content)
            except Exception:
                # If the model returned text, try to extract JSON substring
                try:
                    start = content.find('{')
                    end = content.rfind('}')
                    if start != -1 and end != -1 and end > start:
                        result = json.loads(content[start:end+1])
                    else:
                        raise ValueError("No JSON in reply")
                except Exception as e:
                    _log_info(f"[Review] Invalid reply")
                    return {"status": "error", "error": f"Invalid validator reply: {e}", "raw": content}

            approved = bool(result.get("approved"))
            reasons = result.get("reasons") if isinstance(result.get("reasons"), list) else []
            revised = result.get("revised_plan") if isinstance(result.get("revised_plan"), list) else None

            applied_plan = None
            if revised and not approved:
                # Apply revised plan to UI (extract titles only)
                formatted = []
                for i, step in enumerate(revised):
                    if isinstance(step, dict):
                        title = step.get("title", step.get("description", str(step)))
                    else:
                        title = str(step)
                    formatted.append({"id": i+1, "title": title, "done": False})
                self.task_list = formatted
                applied_plan = formatted
                if self.on_plan_update:
                    self.on_plan_update(self.task_list)

            # Logs and brief chat line
            status_txt = "Approved" if approved else "Needs revision"
            _log_info(f"[Review] {status_txt} — reasons: {len(reasons)} — revised_applied: {bool(applied_plan)}")
            if self.on_assistant_message:
                try:
                    if approved:
                        self.on_assistant_message("🧪 Plan review: Approved ✅")
                    else:
                        brief = ("; ".join(reasons[:2])) if reasons else "issues detected"
                        self.on_assistant_message(f"🧪 Plan review: Changes required ❌ — {brief}")
                except Exception:
                    pass

            result_payload = {
                "status": "success",
                "approved": approved,
                "reasons": reasons,
                "applied_revision": applied_plan is not None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            return result_payload
        except Exception as e:
            _log_info(f"[Review] ERR -> {e}")
            return {"status": "error", "error": str(e)}
    
    def chat(self, user_message: str) -> str:
        """Main chat function - handles user input and returns response"""
        
        # Add user message to conversation
        self.conversation_history.append({
            "role": "user", 
            "content": user_message
        })
        self.current_task = user_message
        self.current_user_task_text = user_message
        
        # Directly call GPT-OSS and let it decide how to proceed (tools vs. text)
        # No pre-status calls, no injected kitchen state, no pre-planning
        
        # Get GPT-OSS response loop
        gpt_response = self._call_gpt_oss()
        
        # No need to call on_assistant_message here (_call_gpt_oss handles it)
        return gpt_response

    def _plan_tasks(self, user_message: str) -> List[Dict[str, Any]]:
        """Planner disabled: return empty list and let the model drive planning in free-form."""
        return []
    
    def _call_gpt_oss(self) -> str:
        """Call GPT-OSS API with function calling support in a loop until tasks complete"""
        
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
            },
            {
                "type": "function",
                "function": {
                    "name": "update_kitchen_state",
                    "description": "Update remembered kitchen state (assistant-managed)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "state_updates": {"type": "object", "description": "Partial state to merge"}
                        },
                        "required": ["state_updates"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mark_task_complete",
                    "description": "Mark a task id as complete in current plan",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "integer"}
                        },
                        "required": ["task_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_plan",
                    "description": "Get current task list and kitchen state",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_plan",
                    "description": "Create a new task plan for the user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tasks": {
                                "type": "array",
                                "description": "List of tasks to create",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string", "description": "Task description"}
                                    },
                                    "required": ["title"]
                                }
                            }
                        },
                        "required": ["tasks"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "review_plan",
                    "description": "Ask the model to strictly validate the current plan against kitchen_state and optionally return a revised plan.",
                    "parameters": {"type": "object", "properties": {"instructions": {"type": "string"}}}
                }
            }
        ]
        
        max_steps = 20
        step = 0
        
        try:
            while step < max_steps:
                step += 1
                _log_info(f"[GPT] step {step}")
                
                payload = {
                    "model": "gpt-oss:20b",
                    "messages": self.conversation_history,
                    "tools": tools,
                    "tool_choice": "auto",
                    "stream": True
                }
                
                # Stream response for smoother UI
                response = requests.post(self.gpt_oss_url, json=payload, timeout=(10, 600), stream=True)
                if response.status_code != 200:
                    _log_info(f"[HTTP {response.status_code}] stream request failed")
                    # Inform the user in chat and stop gracefully
                    if self.on_assistant_message:
                        try:
                            self.on_assistant_message("I'm having trouble connecting to the model right now (stream error). Please try again.")
                        except Exception:
                            pass
                    return f"HTTP Error {response.status_code}: {response.text}"
                
                # Begin streaming to UI
                if self.on_assistant_stream:
                    try:
                        self.on_assistant_stream({"type": "start"})
                    except Exception:
                        pass
                full_content = ""
                tool_calls_buffer: List[Dict[str, Any]] = []
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        # Some servers prefix with 'data: '
                        if line.startswith("data: "):
                            try:
                                obj = json.loads(line[len("data: "):])
                            except Exception:
                                continue
                        else:
                            continue
                    # Ollama-like streaming fields
                    if obj.get("done") is True:
                        break
                    msg = obj.get("message", {})
                    delta = msg.get("content", "")
                    if delta:
                        full_content += delta
                        if self.on_assistant_stream:
                            try:
                                self.on_assistant_stream({"type": "delta", "text": delta})
                            except Exception:
                                pass
                        # Slow down streaming slightly for better readability
                        time.sleep(0.02)
                    # Capture tool calls if any appear
                    tc = msg.get("tool_calls")
                    if tc:
                        tool_calls_buffer = tc
                # Finish stream
                if self.on_assistant_stream:
                    try:
                        self.on_assistant_stream({"type": "end"})
                    except Exception:
                        pass
                
                # If the assistant emitted tool calls, execute them
                if tool_calls_buffer:
                    _log_info(f"[Tool] {len(tool_calls_buffer)} call(s)")
                    tool_results = []
                    for i, tool_call in enumerate(tool_calls_buffer):
                        function_name = tool_call["function"]["name"]
                        function_args = tool_call["function"].get("arguments", {})
                        # concise argument preview for key tools
                        preview = ""
                        if function_name == "execute_robot_command":
                            if isinstance(function_args, dict):
                                preview = function_args.get("language_instruction", "")[:60]
                        _log_info(f"  ↳ {function_name} {('('+preview+'...)') if preview else ''}")
                        if function_name in self.available_functions:
                            try:
                                if isinstance(function_args, str):
                                    try:
                                        function_args = json.loads(function_args)
                                    except Exception:
                                        pass
                                result_payload = self.available_functions[function_name](**function_args)
                                tool_results.append(result_payload)
                                _log_info(f"  ✓ {function_name}")
                            except Exception as e:
                                error_result = {"status": "error", "error": str(e)}
                                tool_results.append(error_result)
                                _log_info(f"  ✗ {function_name} -> {e}")
                        else:
                            unknown_result = {"status": "error", "error": f"Unknown function: {function_name}"}
                            tool_results.append(unknown_result)
                            _log_info(f"  ✗ Unknown function: {function_name}")
                    # Update history with streamed assistant message and tool calls
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": full_content,
                        "tool_calls": tool_calls_buffer
                    })
                    for i, (tool_call, result_payload) in enumerate(zip(tool_calls_buffer, tool_results)):
                        self.conversation_history.append({
                            "role": "tool",
                            "tool_call_id": f"call_{i}",
                            "name": tool_call["function"]["name"],
                            "content": json.dumps(result_payload)
                        })
                    # Continue loop to let model observe results
                    continue
                else:
                    # No tool calls; finalize text answer
                    if full_content:
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": full_content
                        })
                        return full_content
                    # Fallback: non-streaming request if no streamed content arrived
                    _log_info("[Fallback] No stream content -> non-streaming request")
                    fallback_payload = dict(payload)
                    fallback_payload["stream"] = False
                    try:
                        non_stream_resp = requests.post(self.gpt_oss_url, json=fallback_payload, timeout=30)
                        if non_stream_resp.status_code == 200:
                            parsed = self._parse_gpt_response(non_stream_resp.text)
                            message = parsed.get("message", {})
                            content = message.get("content", "")
                            tool_calls = message.get("tool_calls", [])
                            if tool_calls:
                                _log_info(f"[Tool] {len(tool_calls)} call(s) (fallback)")
                                tool_results = []
                                for i, tool_call in enumerate(tool_calls):
                                    function_name = tool_call["function"]["name"]
                                    function_args = tool_call["function"].get("arguments", {})
                                    preview = ""
                                    if function_name == "execute_robot_command":
                                        if isinstance(function_args, dict):
                                            preview = function_args.get("language_instruction", "")[:60]
                                    _log_info(f"  ↳ {function_name} {('('+preview+'...)') if preview else ''}")
                                    if function_name in self.available_functions:
                                        try:
                                            if isinstance(function_args, str):
                                                try:
                                                    function_args = json.loads(function_args)
                                                except Exception:
                                                    pass
                                            result_payload = self.available_functions[function_name](**function_args)
                                            tool_results.append(result_payload)
                                            _log_info(f"  ✓ {function_name}")
                                        except Exception as e:
                                            error_result = {"status": "error", "error": str(e)}
                                            tool_results.append(error_result)
                                            _log_info(f"  ✗ {function_name} -> {e}")
                                    else:
                                        unknown_result = {"status": "error", "error": f"Unknown function: {function_name}"}
                                        tool_results.append(unknown_result)
                                        _log_info(f"  ✗ Unknown function: {function_name}")
                                # Record and continue
                                self.conversation_history.append({
                                    "role": "assistant",
                                    "content": content,
                                    "tool_calls": tool_calls
                                })
                                for i, (tool_call, result_payload) in enumerate(zip(tool_calls, tool_results)):
                                    self.conversation_history.append({
                                        "role": "tool",
                                        "tool_call_id": f"call_{i}",
                                        "name": tool_call["function"]["name"],
                                        "content": json.dumps(result_payload)
                                    })
                                continue
                            elif content:
                                # Simulate streamed delivery to UI for consistency
                                if self.on_assistant_stream:
                                    try:
                                        self.on_assistant_stream({"type": "start"})
                                        self.on_assistant_stream({"type": "delta", "text": content})
                                        self.on_assistant_stream({"type": "end"})
                                    except Exception:
                                        pass
                                self.conversation_history.append({
                                    "role": "assistant",
                                    "content": content
                                })
                                return content
                        else:
                            _log_info(f"[HTTP {non_stream_resp.status_code}] fallback request failed")
                            if self.on_assistant_message:
                                try:
                                    self.on_assistant_message("I'm having trouble connecting to the model right now (fallback error). Please try again.")
                                except Exception:
                                    pass
                    except Exception as e:
                        _log_info(f"[Fallback] request error -> {e}")
                        if self.on_assistant_message:
                            try:
                                self.on_assistant_message("I'm having trouble connecting to the model right now (network error). Please try again.")
                            except Exception:
                                pass
                    # Nothing usable
                    return "I didn't understand that. Can you try again?"
            
            _log_info("[GPT] Reached maximum step limit")
            return "I executed many steps but reached the maximum step limit. If there's more to do, please continue."
        except Exception as e:
            error_msg = f"Error calling GPT-OSS: {e}"
            _log_info(f"[GPT] ERR -> {e}")
            return error_msg
    
    def _parse_gpt_response(self, response_text: str) -> Dict:
        """Parse GPT-OSS response"""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            return {"message": {"content": response_text}}

# --------------------------
# PyQt5 UI
# --------------------------
class KitchenAssistantUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kitchen Robot Assistant (GPT-OSS)")
        self.resize(1100, 700)
        
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root_layout = QtWidgets.QHBoxLayout(central)
        
        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)
        
        # Left panel (Chat)
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        
        chat_group = QtWidgets.QGroupBox("Chat")
        chat_layout = QtWidgets.QVBoxLayout(chat_group)
        left_layout.addWidget(chat_group, 1)
        
        header_row = QtWidgets.QHBoxLayout()
        header_label = QtWidgets.QLabel("Kitchen Assistant")
        header_label.setStyleSheet("font-weight: bold; font-size: 15px;")
        header_row.addWidget(header_label)
        header_row.addStretch(1)
        chat_layout.addLayout(header_row)
        
        self.chat_history = QtWidgets.QTextEdit()
        self.chat_history.setReadOnly(True)
        # Ensure emoji fonts are preferred when available
        self.chat_history.document().setDefaultStyleSheet(
            """
            .emoji { font-family: 'Noto Color Emoji','Segoe UI Emoji','Apple Color Emoji','DejaVu Sans',sans-serif; }
            b { font-weight: 600; }
            .user { color: #93C5FD; } /* light blue */
            .assistant { color: #A78BFA; } /* lavender */
            """
        )
        chat_layout.addWidget(self.chat_history, 1)
        
        input_row = QtWidgets.QHBoxLayout()
        self.user_input = QtWidgets.QLineEdit()
        send_btn = QtWidgets.QPushButton("Send")
        send_btn.clicked.connect(self.send_message)
        # Pressing Enter sends the message
        self.user_input.returnPressed.connect(self.send_message)
        input_row.addWidget(self.user_input, 1)
        input_row.addWidget(send_btn)
        chat_layout.addLayout(input_row)
        
        # Right panel (Status)
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        status_group = QtWidgets.QGroupBox("Status & Activity")
        status_layout = QtWidgets.QVBoxLayout(status_group)
        right_layout.addWidget(status_group, 1)
        # Ensure the right side (with checklist) starts wider
        right_widget.setMinimumWidth(520)
        
        meta_form = QtWidgets.QGridLayout()
        status_layout.addLayout(meta_form)
        
        meta_form.addWidget(QtWidgets.QLabel("Robot Status:"), 0, 0)
        self.status_value_label = QtWidgets.QLabel("Unknown")
        meta_form.addWidget(self.status_value_label, 0, 1)
        
        meta_form.addWidget(QtWidgets.QLabel("User Task:"), 1, 0)
        self.current_user_task_label = QtWidgets.QLabel("-")
        meta_form.addWidget(self.current_user_task_label, 1, 1)
        
        meta_form.addWidget(QtWidgets.QLabel("Executing:"), 2, 0)
        self.current_executing_label = QtWidgets.QLabel("-")
        meta_form.addWidget(self.current_executing_label, 2, 1)
        
        meta_form.addWidget(QtWidgets.QLabel("Next Step:"), 3, 0)
        self.current_task_label = QtWidgets.QLabel("-")
        meta_form.addWidget(self.current_task_label, 3, 1)
        
        meta_form.addWidget(QtWidgets.QLabel("Plan Approved:"), 4, 0)
        self.plan_approved_label = QtWidgets.QLabel("-")
        meta_form.addWidget(self.plan_approved_label, 4, 1)
        
        # Checklist
        checklist_container = QtWidgets.QWidget()
        checklist_layout = QtWidgets.QVBoxLayout(checklist_container)
        status_layout.addWidget(checklist_container, 1)
        
        checklist_label = QtWidgets.QLabel("Checklist")
        checklist_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        checklist_layout.addWidget(checklist_label)
        self.task_tree = QtWidgets.QTreeWidget()
        self.task_tree.setColumnCount(2)
        self.task_tree.setHeaderLabels(["Done", "Task"])
        self.task_tree.setRootIsDecorated(False)
        self.task_tree.setUniformRowHeights(True)
        # Make task column stretch and reasonably wide by default
        self.task_tree.setColumnWidth(0, 60)
        self.task_tree.setColumnWidth(1, 520)
        self.task_tree.header().setStretchLastSection(True)
        # Remove horizontal scrollbar and elide long text
        self.task_tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.task_tree.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        checklist_layout.addWidget(self.task_tree, 1)
        
        # Kitchen State
        ks_group = QtWidgets.QGroupBox("Kitchen State")
        ks_form = QtWidgets.QGridLayout(ks_group)
        status_layout.addWidget(ks_group)
        
        self.ks_labels: Dict[str, QtWidgets.QLabel] = {
            "cabinet_open": QtWidgets.QLabel("No"),
            "lid_on_pot": QtWidgets.QLabel("Yes"),
            "pineapple_in_pot": QtWidgets.QLabel("No"),
            "salt_added": QtWidgets.QLabel("No")
        }
        row = 0
        ks_form.addWidget(QtWidgets.QLabel("Cabinet Open:"), row, 0)
        ks_form.addWidget(self.ks_labels["cabinet_open"], row, 1); row += 1
        ks_form.addWidget(QtWidgets.QLabel("Lid On Pot:"), row, 0)
        ks_form.addWidget(self.ks_labels["lid_on_pot"], row, 1); row += 1
        ks_form.addWidget(QtWidgets.QLabel("Pineapple In Pot:"), row, 0)
        ks_form.addWidget(self.ks_labels["pineapple_in_pot"], row, 1); row += 1
        ks_form.addWidget(QtWidgets.QLabel("Salt Added:"), row, 0)
        ks_form.addWidget(self.ks_labels["salt_added"], row, 1)
        
        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        status_layout.addLayout(btn_row)
        refresh_btn = QtWidgets.QPushButton("Refresh Status")
        refresh_btn.clicked.connect(self.refresh_status)
        clear_btn = QtWidgets.QPushButton("Clear Checklist")
        clear_btn.clicked.connect(self.clear_checklist)
        btn_row.addStretch(1)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(clear_btn)
        
        # Activity Log
        activity_group = QtWidgets.QGroupBox("Activity Log")
        activity_layout = QtWidgets.QVBoxLayout(activity_group)
        self.activity_log = QtWidgets.QTextEdit()
        self.activity_log.setReadOnly(True)
        activity_layout.addWidget(self.activity_log)
        status_layout.addWidget(activity_group, 1)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([500, 600])
        
        # Queues for thread-safe updates
        self.message_queue: "queue.Queue[str]" = queue.Queue()
        self.status_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.plan_queue: "queue.Queue[List[Dict[str, Any]]]" = queue.Queue()
        self.exec_queue: "queue.Queue[str]" = queue.Queue()
        self.stream_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.log_queue: "queue.Queue[str]" = queue.Queue()
        
        # Instantiate bot with callbacks
        self.bot = GPTOSSChatBot(
            on_assistant_message=self._on_assistant_message,
            on_tool_result=self._on_tool_result,
            on_status_update=self._on_status_update,
            on_plan_update=self._on_plan_update,
            on_execute_start=self._on_execute_start,
            on_assistant_stream=self._on_assistant_stream
        )
        
        # Initial status and kitchen state
        self.refresh_status()
        self._update_kitchen_state_display(self.bot.kitchen_state)
        
        # Timer to poll queues
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._poll_queues)
        self.timer.start(100)

        # Dark theme stylesheet for the entire UI
        self.setStyleSheet(
            """
            QWidget { background-color: #121212; color: #E5E7EB; }
            QGroupBox { border: 1px solid #2A2A2A; border-radius: 6px; margin-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #E5E7EB; font-weight: 700; font-size: 14px; }
            QTextEdit, QLineEdit { background-color: #1E1E1E; color: #E5E7EB; border: 1px solid #2A2A2A; border-radius: 6px; }
            /* Larger, emoji-capable font for chat */
            QTextEdit { font-size: 15px; font-family: 'Inter','Segoe UI','Noto Sans','DejaVu Sans','Noto Color Emoji','Apple Color Emoji','Segoe UI Emoji',sans-serif; }
            QLineEdit { font-size: 14px; font-family: 'Inter','Segoe UI','Noto Sans','DejaVu Sans',sans-serif; }
            QPushButton { background-color: #2563EB; color: #FFFFFF; border: none; padding: 6px 10px; border-radius: 6px; }
            QPushButton:hover { background-color: #1D4ED8; }
            QTreeWidget { background-color: #1E1E1E; border: 1px solid #2A2A2A; border-radius: 6px; }
            QHeaderView::section { background-color: #1F2937; color: #E5E7EB; padding: 6px; border: none; }
            QScrollBar:vertical { background: #1E1E1E; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #374151; min-height: 24px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #4B5563; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            """
        )
        # Make left group title bold too
        chat_group.setStyleSheet("QGroupBox::title { font-weight: 700; font-size: 14px; }")
        status_group.setStyleSheet("QGroupBox::title { font-weight: 700; font-size: 14px; }")
        ks_group.setStyleSheet("QGroupBox::title { font-weight: 700; font-size: 14px; }")
        activity_group.setStyleSheet("QGroupBox::title { font-weight: 700; font-size: 14px; }")

        # Connect activity log sink
        global ACTIVITY_LOG_HOOK
        ACTIVITY_LOG_HOOK = lambda m: self.log_queue.put(m)
        
    def _fmt_bool(self, v: Any) -> str:
        if isinstance(v, bool):
            return "Yes" if v else "No"
        if v is None:
            return "-"
        return str(v)
    
    def _update_kitchen_state_display(self, kitchen_state: Dict[str, Any]):
        for key in ("cabinet_open", "lid_on_pot", "pineapple_in_pot", "salt_added"):
            if key in self.ks_labels:
                self.ks_labels[key].setText(self._fmt_bool(kitchen_state.get(key)))
    
    def append_chat(self, text: str, who: str):
        if who == "user":
            # Blue person emoji for user
            self.chat_history.append(f"<span class='user'><b><span class='emoji'>👤</span> You:</b> {self._escape_html(text)}</span>")
        else:
            # Robot emoji for assistant
            self.chat_history.append(f"<span class='assistant'><b><span class='emoji'>🤖</span> Assistant:</b> {self._escape_html(text)}</span>")
    
    def _escape_html(self, s: str) -> str:
        return (s
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
    
    def render_plan(self, tasks: List[Dict[str, Any]]):
        self.task_tree.clear()
        for t in tasks:
            mark = "☑" if t.get("done") else "☐"
            item = QtWidgets.QTreeWidgetItem([mark, t.get("title", "")])
            self.task_tree.addTopLevelItem(item)
        self.task_tree.resizeColumnToContents(0)
    
    def clear_checklist(self):
        self.task_tree.clear()
    
    def refresh_status(self):
        def worker():
            status = self.bot.get_robot_status()
            self.status_queue.put(status)
        threading.Thread(target=worker, daemon=True).start()
    
    def send_message(self):
        text = self.user_input.text().strip()
        if not text:
            return
        self.user_input.clear()
        self.append_chat(text, who="user")
        self.current_user_task_label.setText(text)
        self.current_executing_label.setText("-")
        
        def worker():
            reply = self.bot.chat(text)
            _ = reply
        threading.Thread(target=worker, daemon=True).start()
    
    # Bot callback handlers (thread-safe: push to queues)
    def _on_assistant_message(self, message: str):
        self.message_queue.put(message)
    
    def _on_assistant_stream(self, evt: Dict[str, Any]):
        # evt: {type: 'start'|'delta'|'end', text?: str}
        self.stream_queue.put(evt)
    
    def _on_tool_result(self, name: str, payload: Dict[str, Any]):
        if name == "execute_robot_command":
            # Optimistic update: mark the next pending task complete on success
            try:
                if isinstance(payload, dict) and payload.get("status") == "success":
                    next_task = next((t for t in self.bot.task_list if not t.get("done")), None)
                    if next_task and isinstance(next_task.get("id"), int):
                        self.bot.mark_task_complete(next_task.get("id"))
            except Exception:
                pass
        elif name == "get_robot_status":
            pass
        elif name == "review_plan":
            try:
                approved = bool(payload.get("approved")) if isinstance(payload, dict) else False
                self.plan_approved_label.setText("Yes" if approved else "No")
                self.plan_approved_label.setStyleSheet(f"color: {'#10B981' if approved else '#F59E0B'};")
            except Exception:
                pass
        else:
            pass
    
    def _on_status_update(self, payload: Dict[str, Any]):
        self.status_queue.put(payload)
        if isinstance(payload, dict) and payload.get("status") == "success" and payload.get("kitchen_state") is not None:
            self._update_kitchen_state_display(payload.get("kitchen_state", {}))
    
    def _on_plan_update(self, plan: List[Dict[str, Any]]):
        self.plan_queue.put(plan)
    
    def _on_execute_start(self, instruction: str):
        self.exec_queue.put(instruction)
    
    def _poll_queues(self):
        # Messages
        try:
            while True:
                msg = self.message_queue.get_nowait()
                if isinstance(msg, str):
                    self.append_chat(msg, who="assistant")
        except queue.Empty:
            pass
        
        # Streaming assistant chunks
        try:
            while True:
                evt = self.stream_queue.get_nowait()
                if not isinstance(evt, dict):
                    continue
                etype = evt.get("type")
                if etype == "start":
                    self._streaming_begin()
                elif etype == "delta":
                    self._streaming_append(evt.get("text", ""))
                elif etype == "end":
                    self._streaming_end()
        except queue.Empty:
            pass
        
        # Status updates
        try:
            while True:
                status = self.status_queue.get_nowait()
                if isinstance(status, dict) and status.get("status") == "success":
                    robot_status = status.get("robot_status")
                    if isinstance(robot_status, str):
                        trimmed = robot_status[:64] + ("…" if len(robot_status) > 64 else "")
                        self.status_value_label.setText(trimmed)
                    else:
                        self.status_value_label.setText("OK")
                elif isinstance(status, dict) and status.get("status") == "error":
                    self.status_value_label.setText(f"Error: {status.get('error')}")
                else:
                    self.status_value_label.setText("Unknown")
        except queue.Empty:
            pass
        
        # Plan updates
        try:
            while True:
                plan = self.plan_queue.get_nowait()
                if isinstance(plan, list):
                    self.render_plan(plan)
                    next_task = next((t for t in plan if not t.get("done")), None)
                    self.current_task_label.setText(next_task["title"] if next_task else "All tasks complete")
        except queue.Empty:
            pass
        
        # Executing updates
        try:
            while True:
                instr = self.exec_queue.get_nowait()
                self.current_executing_label.setText(instr)
        except queue.Empty:
            pass
        
        # Activity log updates
        try:
            while True:
                log = self.log_queue.get_nowait()
                if isinstance(log, str):
                    self.activity_log.append(log)
                    self.activity_log.ensureCursorVisible()
        except queue.Empty:
            pass

    def _streaming_begin(self):
        # Only mark stream open; defer inserting prefix until first delta arrives
        self._stream_open = True
        self._stream_started = False

    def _streaming_append(self, text: str):
        if not text:
            return
        # Sanitize chunk: on first chunk, strip leading whitespace/newlines
        if not self._stream_started:
            text = text.lstrip()
            if not text:
                return
        # Collapse excessive blank lines to avoid large gaps
        text = text.replace("\r\n", "\n")
        # If the chunk is only whitespace/newlines, limit to a single newline
        if text.strip() == "":
            if self._stream_last_was_blank:
                return
            text = "\n"
            self._stream_last_was_blank = True
        else:
            # Reduce any 3+ consecutive newlines inside the chunk to a single blank line
            while "\n\n\n" in text:
                text = text.replace("\n\n\n", "\n\n")
            self._stream_last_was_blank = False
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.End)
        if not self._stream_started:
            # Ensure assistant starts on a new line and insert prefix once
            cursor.insertBlock()
            html = "<span class='assistant'><b><span class='emoji'>🤖</span> Assistant:</b> "
            cursor.insertHtml(html)
            self._stream_started = True
        cursor.insertText(text)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

    def _streaming_end(self):
        if self._stream_started:
            cursor = self.chat_history.textCursor()
            cursor.movePosition(cursor.End)
            cursor.insertHtml("</span>")
            cursor.insertBlock()
            self.chat_history.setTextCursor(cursor)
            self.chat_history.ensureCursorVisible()
        # Reset flags regardless
        self._stream_open = False
        self._stream_started = False
        self._stream_last_was_blank = False

# Interactive Chat Interface (PyQt5)
def main():
    app = QtWidgets.QApplication([])
    window = KitchenAssistantUI()
    window.show()
    app.exec()

if __name__ == "__main__":
    main()
