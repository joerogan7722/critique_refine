# Role Prompts

This directory contains the prompt templates for the various roles that can be used with the CritiqueRefineTool.

## Roles

### general_critic.txt
*   **Purpose**: Provides general critique on a given text.
*   **Expected Input**: A string of text.
*   **Expected Output**: A string of text with a critique of the input.
*   **Example Usage**:
    ```
    Input: "The quick brown fox jumps over the lazy dog."
    Output: "This sentence is grammatically correct, but it is a cliché. Consider using a more original sentence to engage the reader."
    ```

### refiner.txt
*   **Purpose**: Refines a given text to improve its clarity, conciseness, and overall quality.
*   **Expected Input**: A string of text.
*   **Expected Output**: A string of text with the refined version of the input.
*   **Example Usage**:
    ```
    Input: "The report was read by me."
    Output: "I read the report."
    ```

### style_critic.txt
*   **Purpose**: Focuses on the style of a given text, providing feedback on its tone, voice, and other stylistic elements.
*   **Expected Input**: A string of text.
*   **Expected Output**: A string of text with a critique of the style of the input.
*   **Example Usage**:
    ```
    Input: "The data indicates a significant increase in sales."
    Output: "The tone of this sentence is very formal. Consider using a more conversational tone to connect with the reader, for example: 'Our sales have skyrocketed!'"
    ```

### planner.txt
*   **Purpose**: Helps to plan a project or task, breaking it down into smaller, more manageable steps.
*   **Expected Input**: A string of text describing a goal or project.
*   **Expected Output**: A string of text with a step-by-step plan to achieve the goal.
*   **Example Usage**:
    ```
    Input: "I want to build a website."
    Output: "1. Define the purpose and goals of the website. 2. Choose a domain name and web hosting provider. 3. Design the website layout and user interface. 4. Write the website content. 5. Develop the website using HTML, CSS, and JavaScript. 6. Test the website and deploy it."
    ```

### meta_critic.txt
*   **Purpose**: Provides feedback on the feedback provided by other critics, helping to ensure that it is fair, accurate, and helpful.
*   **Expected Input**: A string of text containing a critique.
*   **Expected Output**: A JSON object with the following format: `{"actionable": true/false, "summary": "A brief summary of the critique.", "suggestions": ["A list of concrete suggestions for improvement."]}`
*   **Example Usage**:
    ```
    Input: "This sentence is bad."
    Output: {"actionable": false, "summary": "The critique is not specific enough to be actionable.", "suggestions": ["Provide specific reasons why the sentence is bad and offer concrete suggestions for improvement."]}
    ```

### music_critic.txt
*   **Purpose**: For critique of lyrics, vocals, or musical ideas.
*   **Expected Input**: A string of text containing lyrics, a description of a vocal performance, or a musical idea.
*   **Expected Output**: A string of text with a critique of the input.
*   **Example Usage**:
    ```
    Input: "The lyrics are about a broken heart."
    Output: "The theme of a broken heart is very common in music. To make your lyrics stand out, try to use more specific and personal details to tell a unique story."
    ```

### tutor.txt
*   **Purpose**: For learning/explaining difficult concepts.
*   **Expected Input**: A string of text with a question or a concept to be explained.
*   **Expected Output**: A string of text with a clear and concise explanation of the concept.
*   **Example Usage**:
    ```
    Input: "What is a neural network?"
    Output: "A neural network is a type of machine learning model that is inspired by the structure of the human brain. It is composed of interconnected nodes, or neurons, that process information and learn from data."
    ```

## Learning Coach

This role guides users through mastering topics via interactive lessons, questions, and feedback loops.  It focuses on iterative learning and personalized instruction.

### researcher.txt
*   **Purpose**: For summarizing and synthesizing sources (inc. YouTube transcripts, articles).
*   **Expected Input**: A string of text containing the content of a source.
*   **Expected Output**: A string of text with a summary of the source.
*   **Example Usage**:
    ```
    Input: "The article discusses the impact of climate change on the global economy."
    Output: "The article argues that climate change will have a significant negative impact on the global economy, leading to decreased GDP, increased inequality, and greater financial instability."
    ```

### brainstormer.txt
*   **Purpose**: Focused on novelty, idea generation, and iterated expansion.
*   **Expected Input**: A string of text with a topic or a question.
*   **Expected Output**: A string of text with a list of ideas or suggestions related to the topic.
*   **Example Usage**:
    ```
    Input: "What are some new features we can add to our app?"
    Output: "1. A dark mode option. 2. A personalized news feed. 3. A gamification system with rewards and achievements. 4. Integration with other apps and services."
    ```

### code_reviewer.txt
*   **Purpose**: Focused on static analysis, logic, structure, and clarity.
*   **Expected Input**: A string of text containing code.
*   **Expected Output**: A string of text with a review of the code, including suggestions for improvement.
*   **Example Usage**:
    ```
    Input: "def add(a, b): return a + b"
    Output: "The function is correct, but it is missing a docstring. Add a docstring to explain what the function does, its parameters, and what it returns."
    ```

### devils_advocate.txt
*   **Purpose**: Surface flaws, risks, or opposing logic.
*   **Expected Input**: A string of text with a plan, an idea, or an argument.
*   **Expected Output**: A string of text with a critique of the input, pointing out potential flaws, risks, or counterarguments.
*   **Example Usage**:
    ```
    Input: "We should launch our new product next month."
    Output: "Have you considered the risk of launching a new product during the holiday season, when competition is high and consumer spending is focused on gifts? It might be better to wait until after the holidays to launch."
    ```

### user_advocate.txt
*   **Purpose**: Prioritizes usability and accessibility.
*   **Expected Input**: A string of text describing a user interface, a feature, or a workflow.
*   **Expected Output**: A string of text with a critique of the input from a user's perspective, focusing on usability and accessibility.
*   **Example Usage**:
    ```
    Input: "The user has to click five times to complete the task."
    Output: "This workflow is too long and complicated. Consider reducing the number of steps to make it easier for the user to complete the task."
    ```

### efficiency_analyst.txt
*   **Purpose**: Focuses on reducing bloat and complexity.
*   **Expected Input**: A string of text describing a system, a process, or a piece of code.
*   **Expected Output**: A string of text with a critique of the input, focusing on how to reduce bloat and complexity.
*   **Example Usage**:
    ```
    Input: "The application takes 10 seconds to load."
    Output: "The application is too slow. Consider optimizing the code, reducing the number of dependencies, or using a more efficient framework to improve performance."
    ```
