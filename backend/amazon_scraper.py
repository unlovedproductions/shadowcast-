
import httpx
from bs4 import BeautifulSoup
import re
import random
import asyncio
from typing import Dict, List, Any

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/108.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/108.0'
]

async def scrape_amazon_product(url: str) -> Dict[str, Any]:
    # Validate Amazon URL format
    if not re.match(r'^https?://(?:www\.)?amazon\.(?:com|co\.uk|de|fr|ca|in|it|es|com\.au|co\.jp)/.*(?:dp|gp/product)/([A-Z0-9]{10}).*$', url):
        return {"error": "Invalid Amazon product URL provided."}

    headers = {'User-Agent': random.choice(USER_AGENTS)}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=15)
            response.raise_for_status()  # Raise an HTTPStatusError for bad responses (4xx or 5xx)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"error": f"Product not found at URL: {url}"}
        elif e.response.status_code == 503:
            return {"error": "Amazon temporarily blocked the request. Try again later."}
        else:
            return {"error": f"HTTP error occurred: {e}. Status code: {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": f"An unexpected request error occurred: {e}"}

    soup = BeautifulSoup(response.content, 'html.parser')
    
    product_data = {
        "product_name": None,
        "price": None,
        "key_features": [],
        "star_rating": None,
        "number_of_reviews": None,
        "positive_reviews": [],
        "negative_reviews": [],
        "common_praise_themes": "(Requires NLP on full reviews)",
        "common_complaint_themes": "(Requires NLP on full reviews)",
    }

    # Product Name
    product_name_element = soup.find('span', id='productTitle')
    if product_name_element:
        product_data['product_name'] = product_name_element.get_text(strip=True)

    # Price
    # Attempt to find price using common selectors
    price_element = soup.find('span', class_='a-price-whole')
    if price_element:
        price_fraction = soup.find('span', class_='a-price-fraction')
        price_symbol = soup.find('span', class_='a-price-symbol')
        if price_fraction and price_symbol:
            product_data['price'] = f"{price_symbol.get_text(strip=True)}{price_element.get_text(strip=True)}{price_fraction.get_text(strip=True)}"
        else:
            product_data['price'] = price_element.get_text(strip=True) # Fallback if fraction/symbol not found immediately next to whole
    else:
        # Fallback for other price display formats, e.g., 'a-offscreen' for hidden prices
        price_offscreen = soup.find('span', class_='a-offscreen')
        if price_offscreen:
            product_data['price'] = price_offscreen.get_text(strip=True)

    # Key Features / Bullet Points
    feature_elements = soup.select('#feature-bullets li span.a-list-item')
    if not feature_elements:
        # Alternative selector for features, sometimes they are in a different div
        feature_elements = soup.select('div#productOverview_feature_div ul li span.a-list-item')
    for feature in feature_elements:
        product_data['key_features'].append(feature.get_text(strip=True))

    # Star Rating
    star_rating_element = soup.find('span', class_='a-icon-alt')
    if star_rating_element and 'out of 5 stars' in star_rating_element.get_text():
        product_data['star_rating'] = star_rating_element.get_text(strip=True).split(' ')[0]
    else:
        # Fallback for star rating, sometimes in a different element
        star_rating_element_alt = soup.find('i', class_='a-icon-star-small')
        if star_rating_element_alt:
            star_text = star_rating_element_alt.find('span', class_='a-icon-alt')
            if star_text and 'out of 5 stars' in star_text.get_text():
                product_data['star_rating'] = star_text.get_text(strip=True).split(' ')[0]

    # Number of Reviews
    num_reviews_element = soup.find('span', id='acrCustomerReviewText')
    if num_reviews_element:
        product_data['number_of_reviews'] = num_reviews_element.get_text(strip=True).split(' ')[0].replace(',', '')
    else:
        # Fallback for number of reviews
        num_reviews_element_alt = soup.find('a', id='acrCustomerReviewLink')
        if num_reviews_element_alt:
            num_reviews_text = num_reviews_element_alt.get_text(strip=True)
            match = re.search(r'([\d,]+)\s+ratings?', num_reviews_text)
            if match:
                product_data['number_of_reviews'] = match.group(1).replace(',', '')

    # Reviews (Positive and Negative)
    # Amazon's review structure is complex and often requires navigating to a separate reviews page.
    # This attempts to get reviews visible on the main product page, which are usually a summary or top reviews.
    # For a comprehensive list, a separate request to the reviews page would be needed.
    review_blocks = soup.find_all('div', {'data-hook': 'review'}) # Common selector for individual review blocks
    
    positive_count = 0
    negative_count = 0

    for review in review_blocks:
        review_title_element = review.find('a', {'data-hook': 'review-title'}) or review.find('span', {'data-hook': 'review-title'})
        review_text_element = review.find('span', {'data-hook': 'review-body'})
        star_rating_review_element = review.find('i', {'data-hook': 'review-star-rating'}) or review.find('span', class_='a-icon-alt')

        if review_title_element and review_text_element and star_rating_review_element:
            review_title = review_title_element.get_text(strip=True)
            review_text = review_text_element.get_text(strip=True)
            
            star_rating_text = star_rating_review_element.get_text(strip=True)
            match = re.search(r'(\d+\.?\d*)\s+out', star_rating_text)
            rating = float(match.group(1)) if match else 0.0

            review_entry = {
                'title': review_title,
                'text': review_text[:200] # Truncate to 200 characters
            }

            # Classify as positive (4+ stars) or negative (2- stars)
            if rating >= 4.0 and positive_count < 10:
                product_data['positive_reviews'].append(review_entry)
                positive_count += 1
            elif rating <= 2.0 and negative_count < 10:
                product_data['negative_reviews'].append(review_entry)
                negative_count += 1

    return product_data

if __name__ == '__main__':
    async def main():
        # Test with a placeholder URL (will fail without live Amazon access, but demonstrates structure)
        print("\n--- Testing with a placeholder Amazon URL (expecting errors without live access) ---")
        placeholder_url = "https://www.amazon.com/dp/B09B8V1BM3" # Example: Echo Dot (5th Gen)
        result_placeholder = await scrape_amazon_product(placeholder_url)
        import json
        print(json.dumps(result_placeholder, indent=4))

        # Test with an invalid Amazon product URL format
        print("\n--- Testing with an invalid Amazon URL format ---")
        invalid_format_url = "https://www.amazon.com/dp/INVALIDURL"
        result_invalid_format = await scrape_amazon_product(invalid_format_url)
        print(json.dumps(result_invalid_format, indent=4))

        # Test with a non-Amazon URL
        print("\n--- Testing with a non-Amazon URL ---")
        non_amazon_url = "https://www.google.com"
        result_non_amazon = await scrape_amazon_product(non_amazon_url)
        print(json.dumps(result_non_amazon, indent=4))

    asyncio.run(main())
