# Claude-Emulating Agent Instructions for GitHub Copilot Chat

This markdown file contains prompts and workflows to emulate Claude 3 Opus's behavior in GitHub Copilot Chat. Use it as context in your chats by pasting relevant sections or referencing it. Focus on structured prompting and iterative processes to achieve multi-step reasoning, planning, debugging, and reliable code generation.

## Core Prompting Strategies
Use these techniques in Copilot Chat to force Claude-like output: structured, logical, and iterative. Start prompts with "Act as Claude Opus:" to set the persona. Employ chain-of-thought (CoT) for reasoning. Build on conversation history for context.

### Key Prompt Patterns
- **Chain-of-Thought (CoT) Prompting**: Encourages step-by-step thinking.
  - Example: "Act as Claude Opus. Think step by step: 1. Analyze requirements for [task]. 2. Outline edge cases. 3. Propose architecture. 4. Generate code in [language]."

- **Structured Response Format**: Use tags for clarity, like Claude's XML-style outputs.
  - Example: "Respond in this format: <plan>Outline steps</plan> <code>Generated code</code> <explanation>Why this works</explanation>."

- **Context Injection**: Reference selected code or prior chat.
  - Prefix: "Act as an expert AI like Claude Opus: Prioritize accuracy, avoid hallucinations, use long-context reasoning on [selected code or description]."

- **Iteration Commands**: Use built-in slashes for follow-ups.
  - Debug: "/debug [error message]. Suggest fixes step by step."
  - Fix: "/fix [issue]. Explain changes."
  - Tests: "/tests Generate comprehensive unit tests."

### Sample Prompts for Common Tasks
1. **Planning a Feature**:
   - "Act as Claude Opus. Plan a solution for [task, e.g., building a REST API]. List assumptions, steps, risks, and pseudocode. Be thorough."

2. **Code Generation**:
   - "Based on the plan, generate complete code in [language, e.g., Python]. Include comments. Explain decisions inline via CoT."

3. **Debugging**:
   - "Debug this code: [paste code/error]. Think step by step: Identify issues, suggest fixes, provide updated code."

4. **Refactoring**:
   - "Refactor this for efficiency: [paste code]. Explain changes in a structured format: <changes>List diffs</changes> <reasons>Explanations</reasons>."

5. **Edge Case Handling**:
   - "Test hypothetically for edge cases: [list cases]. Update code accordingly."

## Manual Agentic Workflow Process
Follow this iterative process in Copilot Chat to simulate Claude's execution flow. Use multi-turn chats to maintain context.

1. **Planning Phase**:
   - Prompt: "Plan solution for [task]. List steps, assumptions, and pseudocode like Claude: Logical and detailed."
   - Review and refine: "Expand on step [X] with examples."

2. **Implementation Phase**:
   - Follow-up: "Implement the plan: Generate executable code in [language]. Use CoT for decisions."
   - Paste generated code into your file.

3. **Testing/Debugging Phase**:
   - If errors: "/debug [error]. Provide step-by-step fixes and updated code."
   - Hypothetical tests: "Simulate edge cases: [cases]. Suggest improvements."

4. **Optimization Phase**:
   - Prompt: "Optimize/refactor the code for [performance/readability]. Structure response: <optimized_code>Code</optimized_code> <explanations>Changes</explanations>."
   - Generate tests: "/tests for this code."

5. **Iteration Loop**:
   - Continue in the same chat thread to build context.
   - If needed, start a new thread with a summary of prior context.

## Best Practices and Tips
- **Handle Complexity**: For multi-file projects, reference files explicitly (e.g., "Incorporate logic from fileX.cs").
- **Avoid Hallucinations**: Always prompt for "accuracy over speed" and verify outputs manually.
- **Performance**: This workflow can speed up coding for complex tasks.
- **Limitations**: If responses feel shallow, refine prompts with more details or examples.
