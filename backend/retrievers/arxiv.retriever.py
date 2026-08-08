import requests

# Step 1: Define the arXiv API URL
ARXIV_API_URL = "http://export.arxiv.org/api/query?"

# Step 2: Create a function to search arXiv
def search_arxiv(query, max_results=5):
    """
    Search arXiv for papers
    
    Args:
        query: Search term (e.g., "transformers")
        max_results: How many papers to get (default 5)
    
    Returns:
        The response from arXiv API
    """
    
    # Step 3: Build the search parameters
    params = {
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }
    
    # Step 4: Make the GET request to arXiv
    print(f"Searching arXiv for: '{query}'...")
    response = requests.get(ARXIV_API_URL, params=params, verify=False)
    # Step 5: Return the response
    return response


# Step 6: Test it
if __name__ == "__main__":
    result = search_arxiv("transformers", max_results=3)
    print(f"\nStatus Code: {result.status_code}")
    print(f"\nResponse:\n{result.text[:500]}")  # Print first 500 characters