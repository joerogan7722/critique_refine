import streamlit as st
import json
import glob
import os
from pathlib import Path

def display_run_log(log_data):
    """Displays a single structured run log."""
    st.subheader("Run Log Details")
    
    st.markdown(f"**Timestamp:** {log_data.get('timestamp', 'N/A')}")
    st.markdown(f"**Original User Prompt:** {log_data.get('original_user_prompt', 'N/A')}")
    st.markdown(f"**Reason for Stopping:** {log_data.get('reason_for_stopping', 'N/A')}")
    st.markdown(f"**Runtime:** {log_data.get('runtime', 'N/A'):.2f} seconds" if isinstance(log_data.get('runtime'), (int, float)) else f"**Runtime:** {log_data.get('runtime', 'N/A')}")

    st.markdown("---")
    st.markdown("#### Initial Generation")
    st.code(log_data.get('initial_generation', {}).get('text', 'N/A'), language='text')

    st.markdown("---")
    st.markdown("#### Critiques")
    if log_data.get('critiques'):
        for i, critique in enumerate(log_data['critiques']):
            st.markdown(f"##### Round {critique.get('round', i+1)}")
            st.markdown(f"**Model Used:** {critique.get('model_used', 'N/A')}")
            st.markdown(f"**Roles Used:** {', '.join(critique.get('role_prompt_file_used', ['N/A']))}")
            st.code(critique.get('text', 'N/A'), language='text')
    else:
        st.info("No critiques found for this run.")

    st.markdown("---")
    st.markdown("#### Refinements")
    if log_data.get('refinements'):
        for i, refinement in enumerate(log_data['refinements']):
            st.markdown(f"##### Round {refinement.get('round', i+1)}")
            st.markdown(f"**Model Used:** {refinement.get('model_used', 'N/A')}")
            st.code(refinement.get('text', 'N/A'), language='text')
    else:
        st.info("No refinements found for this run.")
    
    st.markdown("---")
    st.markdown("#### Final Output")
    st.code(log_data.get('final_output', 'N/A'), language='text')

    st.markdown("---")
    st.markdown("#### Configuration Used")
    st.json(log_data.get('config_used', {}))


st.title("CritiqueRefineTool Log Viewer")

# Define log directories
log_dirs = ["logs", "reviews/self-improve"]
all_log_files = []

for log_dir in log_dirs:
    if not os.path.exists(log_dir):
        st.warning(f"Log directory '{log_dir}' not found.")
    else:
        # Collect .jsonl files (for main runs) and .json files (for self-review runs)
        all_log_files.extend(glob.glob(os.path.join(log_dir, "*.jsonl")))
        all_log_files.extend(glob.glob(os.path.join(log_dir, "*.json")))

all_log_files.sort(key=os.path.getmtime, reverse=True) # Sort by modification time, newest first

if all_log_files:
    selected_file_path = st.selectbox("Select a log file:", all_log_files)
    if selected_file_path:
        st.write(f"Displaying log from: {selected_file_path}")
        try:
            # Handle both .jsonl (multiple logs per file) and .json (single log per file)
            file_extension = Path(selected_file_path).suffix
            
            if file_extension == ".jsonl":
                with open(selected_file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f):
                        try:
                            log_entry = json.loads(line)
                            st.markdown(f"### Log Entry {line_num + 1}")
                            display_run_log(log_entry)
                            st.markdown("---") # Separator between multiple logs in a .jsonl file
                        except json.JSONDecodeError:
                            st.warning(f"Error decoding JSON from line {line_num + 1} in {selected_file_path}: {line.strip()}")
            elif file_extension == ".json":
                with open(selected_file_path, 'r', encoding='utf-8') as f:
                    log_entry = json.load(f)
                    display_run_log(log_entry)
            else:
                st.error(f"Unsupported file type: {file_extension}")

        except FileNotFoundError:
            st.error(f"Log file not found at {selected_file_path}")
        except json.JSONDecodeError:
            st.error(f"Error decoding JSON from {selected_file_path}. Please ensure it's a valid JSON/JSONL file.")
        except Exception as e:
            st.error(f"An unexpected error occurred while reading the file: {e}")
else:
    st.info("No .json or .jsonl log files found in the 'logs' or 'reviews/self-improve' directories.")
