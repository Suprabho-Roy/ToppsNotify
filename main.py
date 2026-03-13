from curl_cffi import requests
from bs4 import BeautifulSoup
import os
import time
import random

# --- CONFIGURATION ---
FILE_NAME = "known_products.txt"

# This pulls the data safely from GitHub Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")


def send_telegram_alert(product_name, product_url):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"🚨 NEW TOPPS DROP DETECTED!\n\n{product_name}\n{product_url}"
    }
    try:
        requests.post(api_url, data=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")


def scrape_sitemap_recursively(url, visited=None):
    if visited is None:
        visited = set()

    if url in visited:
        return {}
    visited.add(url)

    print(f"Checking sitemap: {url}")
    products_found = {}

    try:
        # Using chrome110 for maximum stability
        response = requests.get(url, impersonate="chrome110", timeout=30)
        if response.status_code != 200:
            return products_found

        soup = BeautifulSoup(response.content, 'xml')

        for loc in soup.find_all('loc'):
            link = loc.text.strip()

            # If it's another sitemap, dive deeper
            if link.endswith('.xml'):
                # Short human-like delay before hitting the next sitemap
                time.sleep(random.uniform(1.0, 2.5))
                products_found.update(scrape_sitemap_recursively(link, visited))

            # If it's a real product link
            elif '/products/' in link and not link.endswith('.xml'):
                handle = link.split('/products/')[-1]

                # Get title from image tag if available
                parent = loc.parent
                title_tag = parent.find('image:title') if parent else None

                if title_tag and title_tag.text:
                    title = title_tag.text
                else:
                    title = handle.replace('-', ' ').title()

                products_found[handle] = {"title": title, "link": link}

    except Exception as e:
        print(f"Error scanning {url}: {e}")

    return products_found

def main():
    print("--- Starting Topps India Hourly Sniper Loop ---")
    
    # Run 11 times, waiting 5 minutes in between (total ~55 mins)
    for cycle in range(11):
        print(f"\n[Cycle {cycle + 1}/11] Checking Topps Sitemap...")
        
        master_url = "https://in.topps.com/sitemap.xml"
        current_products = scrape_sitemap_recursively(master_url)
        
        if not current_products:
            print("Scan failed. Waiting for next cycle.")
        else:
            # Baseline check
            if not os.path.exists(FILE_NAME):
                with open(FILE_NAME, "w", encoding="utf-8") as f:
                    for handle in current_products.keys():
                        f.write(f"{handle}\n")
                print(f"Baseline set with {len(current_products)} products.")
            else:
                # Load known products
                with open(FILE_NAME, "r", encoding="utf-8") as f:
                    known_products = set(line.strip() for line in f if line.strip())

                # Detect new items
                current_handles = set(current_products.keys())
                new_handles = current_handles - known_products

                if new_handles:
                    print(f"Found {len(new_handles)} NEW products!")
                    for handle in new_handles:
                        item = current_products[handle]
                        print(f"Alerting: {item['title']}")
                        send_telegram_alert(item['title'], item['link'])
                        
                        # Add new item
                        with open(FILE_NAME, "a", encoding="utf-8") as f:
                            f.write(f"{handle}\n")
                else:
                    print("No new products found this cycle.")
        
        # Don't sleep on the very last cycle so the GitHub Action can finish
        if cycle < 10:
            print("Waiting 5 minutes before next check...")
            time.sleep(300) # 300 seconds = 5 minutes

if __name__ == "__main__":
    main()

