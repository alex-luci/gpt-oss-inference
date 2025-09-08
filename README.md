# GPT-OSS Kitchen Assistant

**An autonomous robot kitchen assistant powered by GPT-OSS and GR00T N1.5**

We built a fully autonomous kitchen robot that can understand natural language requests, create detailed execution plans, validate them through AI review, and execute complex cooking tasks without human intervention.

## The Problem We Solved

Traditional kitchen robots require extensive hardcoded logic for each task. Our solution eliminates this by creating a truly autonomous system where the AI handles planning, validation, and execution entirely through natural language reasoning.

## How It Works

When you ask for something like "make a pineapple smoothie," here's what happens:

**Planning Phase**: The AI creates a step-by-step plan using only canonical robot commands that GR00T understands perfectly. No ambiguous instructions - every command is precise.

**Validation Phase**: A separate AI reviewer checks the plan for logical ordering, missing steps, and safety considerations. If issues are found, it provides minimal corrections rather than rejecting the entire plan.

**Execution Phase**: Once approved, the system executes the plan autonomously, updating kitchen state and tracking progress in real-time.

## Technical Architecture

The system uses PyQt5 for the interface and communicates with both the GPT-OSS chat API and the robot's control socket. The UI shows live status updates, execution progress, and maintains a complete activity log.

**Key Innovation**: We enforce canonical command patterns - exact phrases that GR00T recognizes without interpretation errors. Commands like "Open the left cabinet door" or "Pick up the green pineapple from the left cabinet and place it in the gray recipient" ensure 100% reliability.

The AI tracks kitchen state dynamically, updating ingredient locations, container status, and task completion. Everything flows through natural language reasoning rather than predetermined decision trees.

## What Makes This Special

**Zero Hardcoded Logic**: Unlike traditional systems, there's no task-specific programming. The same AI handles making smoothies, preparing salads, or any other kitchen task through pure reasoning.

**Self-Validating**: The built-in review system catches planning errors before execution, making it safe and reliable for real kitchen environments.

**Human-Friendly Interface**: The dark-themed UI shows exactly what's happening - current robot status, execution progress, kitchen state, and a complete activity log. No technical jargon, just clear status updates.

This represents a fundamental shift from programmed robots to truly intelligent kitchen assistants that understand, plan, and execute like a human would - but with perfect consistency and safety validation.