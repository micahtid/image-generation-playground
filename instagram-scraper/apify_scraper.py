import time

import requests

from config import APIFY_API_KEY, APIFY_ACTOR_ID, INSTAGRAM_PROFILE, MAX_POSTS, MAX_IMAGES_PER_POST


def scrape_instagram_posts():
    """
    Scrape Instagram posts using Apify API.
    Returns a list of posts with limited images.
    """

    # Prepare the input for Apify actor
    # Note: Optional fields should be omitted entirely, not set to None
    actor_input = {
        "directUrls": [INSTAGRAM_PROFILE],
        "resultsType": "posts",  # Only posts, no Reels
        "resultsLimit": MAX_POSTS,
        "addParentData": False
    }

    # Start the actor run
    run_url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs"
    headers = {
        "Content-Type": "application/json"
    }
    params = {
        "token": APIFY_API_KEY
    }

    print(f"Starting Apify actor to scrape {INSTAGRAM_PROFILE}...")
    response = requests.post(run_url, json=actor_input, headers=headers, params=params)

    if response.status_code != 201:
        raise Exception(f"Failed to start actor: {response.text}")

    run_data = response.json()
    run_id = run_data["data"]["id"]
    default_dataset_id = run_data["data"]["defaultDatasetId"]

    print(f"Actor run started with ID: {run_id}")
    print("Waiting for actor to finish...")

    # Wait for the actor to finish
    status_url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs/{run_id}"
    while True:
        status_response = requests.get(status_url, params=params)
        status_data = status_response.json()
        status = status_data["data"]["status"]

        if status in ["SUCCEEDED", "FAILED", "ABORTED"]:
            print(f"Actor run finished with status: {status}")
            break

        print(f"Current status: {status}. Waiting...")
        time.sleep(5)

    if status != "SUCCEEDED":
        raise Exception(f"Actor run failed with status: {status}")

    # Fetch the results from the dataset
    dataset_url = f"https://api.apify.com/v2/datasets/{default_dataset_id}/items"
    dataset_response = requests.get(dataset_url, params=params)

    if dataset_response.status_code != 200:
        raise Exception(f"Failed to fetch dataset: {dataset_response.text}")

    posts = dataset_response.json()
    print(f"Retrieved {len(posts)} posts")

    # Process and limit images per post
    processed_posts = []
    for post in posts:
        # Limit images to MAX_IMAGES_PER_POST
        if 'images' in post and isinstance(post['images'], list):
            post['images'] = post['images'][:MAX_IMAGES_PER_POST]

        # Also check for displayUrl and childPosts (carousel posts)
        if 'childPosts' in post and isinstance(post['childPosts'], list):
            post['childPosts'] = post['childPosts'][:MAX_IMAGES_PER_POST]

        processed_posts.append(post)

    return processed_posts


if __name__ == "__main__":
    posts = scrape_instagram_posts()
    print(f"\nScraped {len(posts)} posts successfully!")
    for i, post in enumerate(posts, 1):
        print(f"\nPost {i}:")
        print(f"  URL: {post.get('url', 'N/A')}")
        print(f"  Caption: {post.get('caption', 'N/A')[:100]}...")
        print(f"  Images: {len(post.get('images', []))}")
