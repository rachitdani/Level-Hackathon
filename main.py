import random
import pandas as pd
import streamlit as st
from astrapy import DataAPIClient
from langchain_openai import ChatOpenAI
from langchain.prompts.chat import ChatPromptTemplate
from dotenv import load_dotenv
import os
import cassio

# Load environment variables from .env file
load_dotenv()

# Initialize Astra DB connection
def init_astra_connection():
    ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    ASTRA_DB_ID = os.getenv("ASTRA_DB_ID")
    cassio.init(token=ASTRA_DB_APPLICATION_TOKEN, database_id=ASTRA_DB_ID)

# Generate random engagement data
def generate_engagement_data(num_rows=1000):
    engagement_data = {
        'post_id': list(range(1, num_rows + 1)),
        'post_type': [random.choice(["Photo Posts","Video Posts","Carousel Posts","Instagram Stories","Instagram Reels","Instagram Live","IGTV","Instagram Shopping Posts","Instagram Ads"]) for _ in range(num_rows)],
        'likes': [random.randint(50, 1000) for _ in range(num_rows)],
        'shares': [random.randint(5, 200) for _ in range(num_rows)],
        'comments': [random.randint(1, 500) for _ in range(num_rows)]
    }
    df = pd.DataFrame(engagement_data)
    df.to_csv("engagement_data.csv", index=False)
    return df

# Initialize Astra DB client
def init_db_client():
    client = DataAPIClient(os.getenv("ASTRA_DB_APPLICATION_TOKEN"))
    db = client.get_database_by_api_endpoint(
        "https://84fa67e8-00d5-46b8-9283-e28598a5dd00-us-east-2.apps.astra.datastax.com"
    )
    return db

# Insert data into Astra DB collection
def insert_data_into_db(df, db):
    collection = db.get_collection("social_media_data")
    data_dict = df.to_dict(orient="records")
    collection.insert_many(data_dict)
    print(f"Inserted {len(data_dict)} records into the collection.")

# Fetch post performance for a specific post type from Astra DB
def analyze_post_performance(post_type, db):
    collection = db.get_collection("social_media_data")
    documents = collection.find({"post_type": post_type})
    
    metrics = {"likes": 0, "shares": 0, "comments": 0}
    count = 0
    for doc in documents:
        metrics["likes"] += doc["likes"]
        metrics["shares"] += doc["shares"]
        metrics["comments"] += doc["comments"]
        count += 1
    
    if count > 0:
        metrics = {key: value / count for key, value in metrics.items()}
    
    return metrics

# Calculate percentage difference between two metrics
def calculate_percentage_difference(old_value, new_value):
    if old_value == 0:
        return 0 
    return ((new_value - old_value) / old_value) * 100

# Generate insights using ChatGPT
def generate_insights(metrics, selected_metrics, post_type, comparison):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    chat = ChatOpenAI(temperature=0.7, model="gpt-4o", openai_api_key=openai_api_key)

    # Calculate percentage differences between selected post type and others
    comparison_data = {} 
    for post, post_metrics in comparison.items():
        if post == post_type: #Skipping the current post type
            continue
        likes_diff = calculate_percentage_difference(post_metrics["likes"], selected_metrics["likes"])
        shares_diff = calculate_percentage_difference(post_metrics["shares"], selected_metrics["shares"])
        comments_diff = calculate_percentage_difference(post_metrics["comments"], selected_metrics["comments"])
        
        comparison_data[post] = {
            "likes_diff": likes_diff,
            "shares_diff": shares_diff,
            "comments_diff": comments_diff
        }

    # Format the comparison data into a string for inclusion in the prompt
    comparison_data_str = ""
    for post, data in comparison_data.items():
        comparison_data_str += f"- {post.capitalize()} Posts: Likes: {data['likes_diff']:.2f}%, Shares: {data['shares_diff']:.2f}%, Comments: {data['comments_diff']:.2f}%; "
    
    comparison_data_str = comparison_data_str.strip()

    prompt = ChatPromptTemplate.from_template("""
    You are an expert in social media post performance analysis. Based on the following average engagement metrics for {post_type} posts, provide insights and suggest how this post type performs overall:
    - Average Likes: {likes}
    - Average Shares: {shares}
    - Average Comments: {comments}

    Additionally, compare this post type with other post types and provide insights based on the following percentage differences in engagement:
    {comparison_data}
    
    Provide a bullet-point summary of the performance insights for {post_type} posts, including how this post type compares with others in terms of likes, shares, and comments.
    """)

    response = chat.invoke(
        prompt.format_prompt(
            post_type=post_type.capitalize(),
            likes=metrics["likes"],
            shares=metrics["shares"],
            comments=metrics["comments"],
            comparison_data=comparison_data_str
        ).to_messages()
    )

    general_insight = response.content
    return general_insight


# Compare selected post type's metrics with others
def compare_post_types(selected_post_type, db, post_types):
    comparison = {}
    
    for post_type in post_types:
        if post_type == selected_post_type:
            continue
        metrics = analyze_post_performance(post_type, db)
        comparison[post_type] = metrics
    
    return comparison

if __name__ == "__main__":
    st.title("Social Media Post Performance Analyzer")

    st.sidebar.header("Choose Post Type")
    post_types = ["Photo Posts","Video Posts","Carousel Posts","Instagram Stories","Instagram Reels","Instagram Live","IGTV","Instagram Shopping Posts","Instagram Ads"]
    selected_post_type = st.sidebar.selectbox("Select a post type:", post_types)

    if st.sidebar.button("Analyze"):
        df = generate_engagement_data()

        db = init_db_client()
        #insert_data_into_db(df, db)
        
        st.write(f"Analyzing {selected_post_type} posts...")

        # Get metrics for selected post type
        selected_metrics = analyze_post_performance(post_type=selected_post_type, db=db)
        st.write("Average Engagement Metrics for Selected Post Type:")
        st.write(f"Likes: {selected_metrics['likes']:.2f}")
        st.write(f"Shares: {selected_metrics['shares']:.2f}")
        st.write(f"Comments: {selected_metrics['comments']:.2f}")

        # Generate insights for selected post type
        comparison = compare_post_types(selected_post_type, db, post_types)
        insights = generate_insights(selected_metrics, selected_metrics, selected_post_type, comparison)
        st.subheader("Insights and Comparison:")
        st.write(insights)
