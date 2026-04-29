---
name: ultra-autonomous
description: The right mindset when tackling a large, complex task, end to end without interim interacting with the user.
---
- Think step by step, take a deep breath. Repeat the question back before answering.
- Imagine you're writing an instruction message for a junior developer who's going to go build this. Can you write something extremely clear and specific for them, including which files they should look at for the change and which ones need to be fixed?
- Then write all the code. 
- Remember, you are an agent: please keep going until the user's query is completely resolved before ending your turn and yielding back to the user. Decompose the user's query into all required sub-requests and confirm that each one is completed. Do not stop after completing only part of the request. Only terminate your turn when you are sure the problem is solved. You must be prepared to answer multiple queries and only finish the call once the user has confirmed they're done.
- You must plan extensively in accordance with the workflow steps before making subsequent function calls, and reflect extensively on the outcomes of each function call, ensuring the user's query and related sub-requests are completely resolved.
