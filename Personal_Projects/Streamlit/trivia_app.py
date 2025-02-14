import streamlit as st
import requests
import random

def get_categories():
    response = requests.get("https://opentdb.com/api_category.php")
    if response.status_code == 200:
        return response.json().get("trivia_categories", [])
    return []

def get_questions(category, num_questions):
    url = f"https://opentdb.com/api.php?amount={num_questions}&category={category}&type=multiple"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("results", [])
    return []

def main():
    st.title("Trivia Bot 🧠")
    
    categories = get_categories()
    category_map = {c["name"]: c["id"] for c in categories}
    category_name = st.selectbox("Choose a category:", list(category_map.keys()))
    category_id = category_map[category_name]
    num_questions = st.slider("Number of questions:", 1, 10, 5)
    
    if st.button("Start Trivia!"):
        questions = get_questions(category_id, num_questions)
        score = 0
        
        for i, q in enumerate(questions):
            st.subheader(f"Question {i+1}:")
            options = q['incorrect_answers'] + [q['correct_answer']]
            random.shuffle(options)
            user_answer = st.radio(q['question'], options, key=i)
            
            if st.button(f"Submit {i+1}"):
                if user_answer == q['correct_answer']:
                    score += 1
                    st.success("Correct! ✅")
                else:
                    st.error(f"Wrong ❌ The correct answer is: {q['correct_answer']}")
        
        st.subheader(f"Final Score: {score}/{num_questions}")

if __name__ == "__main__":
    main()