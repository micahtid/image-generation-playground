import json
from datetime import datetime

from apify_scraper import scrape_instagram_posts
from gemini_analyzer import analyze_posts_with_categories
from config import OUTPUT_DIR


def clear_output_directory():
    """Clear all files from the output directory."""
    if OUTPUT_DIR.exists():
        for file in OUTPUT_DIR.iterdir():
            if file.is_file():
                file.unlink()
        print("Cleared previous output files")
    OUTPUT_DIR.mkdir(exist_ok=True)


def clear_design_analysis_only():
    """Clear only design_analysis files (including main.json and category files), keep raw_posts."""
    if OUTPUT_DIR.exists():
        for file in OUTPUT_DIR.iterdir():
            if file.is_file() and (
                file.name.startswith("design_analysis_") or
                file.name == "main.json" or
                file.name.startswith("category_")
            ):
                file.unlink()
        print("Cleared previous design analysis files")


def get_latest_raw_posts():
    """Find and load the most recent raw_posts file."""
    if not OUTPUT_DIR.exists():
        return None

    raw_posts_files = list(OUTPUT_DIR.glob("raw_posts_*.json"))
    if not raw_posts_files:
        return None

    # Get the most recent file
    latest_file = max(raw_posts_files, key=lambda p: p.stat().st_mtime)

    with open(latest_file, 'r', encoding='utf-8') as f:
        posts = json.load(f)

    print(f"Loaded existing data from: {latest_file.name}")
    return posts


def main():
    """
    Main orchestration script that:
    1. Optionally scrapes Instagram posts using Apify (or reuses existing data)
    2. Analyzes the posts with Gemini
    3. Saves the analysis to a JSON file
    """

    print("=" * 60)
    print("Instagram Post Design Pattern Analyzer")
    print("=" * 60)
    print()

    # Check if existing data is available
    existing_posts = get_latest_raw_posts()
    rescrape = True

    if existing_posts is not None:
        print(f"Found existing data with {len(existing_posts)} posts.")
        user_input = input("Do you want to RESCRAPE the data? (y/n): ").strip().lower()

        if user_input in ['n', 'no']:
            rescrape = False
            posts = existing_posts
            print("Using existing scraped data")
            # Only clear design analysis files
            clear_design_analysis_only()
        else:
            rescrape = True
            print("Will rescrape fresh data")
            # Clear all output files
            clear_output_directory()
    else:
        print("No existing data found. Will scrape fresh data.")
        OUTPUT_DIR.mkdir(exist_ok=True)

    # Step 1: Scrape Instagram posts (if needed)
    if rescrape:
        print()
        print("STEP 1: Scraping Instagram posts...")
        print("-" * 60)
        try:
            posts = scrape_instagram_posts()
            print(f"Successfully scraped {len(posts)} posts")
        except Exception as e:
            print(f"Error scraping posts: {e}")
            return

        # Save raw posts data
        raw_posts_file = OUTPUT_DIR / f"raw_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(raw_posts_file, 'w', encoding='utf-8') as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)
        print(f"Raw posts saved to: {raw_posts_file}")
        print()
    else:
        print()
        print("STEP 1: Using existing scraped data")
        print("-" * 60)
        print(f"Loaded {len(posts)} posts from previous scrape")
        print()

    # Step 2: Analyze with Gemini (Two-Phase Category Analysis)
    print("STEP 2: Analyzing design patterns with category detection...")
    print("-" * 60)
    try:
        from config import INSTAGRAM_PROFILE
        main_json, category_jsons = analyze_posts_with_categories(posts, INSTAGRAM_PROFILE)
        print("Two-phase analysis complete")
    except Exception as e:
        print(f"Error analyzing posts: {e}")
        return

    # Step 3: Save analysis results (split into main + category files)
    print()
    print("STEP 3: Saving analysis results...")
    print("-" * 60)

    # Save main JSON
    main_file = OUTPUT_DIR / "main.json"
    with open(main_file, 'w', encoding='utf-8') as f:
        json.dump(main_json, f, indent=2, ensure_ascii=False)
    print(f"Main design system saved to: {main_file}")

    # Save each category JSON
    category_files = []
    for category_id, category_json in category_jsons.items():
        category_file = OUTPUT_DIR / f"category_{category_id}.json"
        with open(category_file, 'w', encoding='utf-8') as f:
            json.dump(category_json, f, indent=2, ensure_ascii=False)
        category_files.append(category_file)
        print(f"Category '{category_id}' saved to: {category_file}")

    # Print summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Posts analyzed: {len(posts)}")
    if rescrape:
        print(f"Raw data: {raw_posts_file}")
    else:
        print("Raw data: (reused existing)")
    print(f"Main design system: {main_file}")
    print(f"Category files: {len(category_files)} files")
    for cf in category_files:
        print(f"  - {cf.name}")
    print()

    # Print a preview of the analysis
    print("Category Analysis Summary:")
    print("-" * 60)
    print(f"  Organization: {main_json.get('organization_name', 'N/A')}")
    print(f"  Categories detected: {len(category_jsons)}")
    print()

    # Print each category
    for i, (category_id, cat_json) in enumerate(category_jsons.items(), 1):
        cat_info = cat_json.get('category_info', {})
        print(f"Category {i}: {cat_info.get('category_name', 'Unknown')}")
        print(f"  ID: {category_id}")
        print(f"  Posts: {cat_info.get('post_count', 0)} ({', '.join(map(str, cat_info.get('posts_included', [])))})")

        purpose_analysis = cat_json.get('purpose_analysis', {})
        print(f"  Purpose: {purpose_analysis.get('purpose', 'Unknown')}")

        # Print logo consistency if available
        if 'consistency_tracking' in cat_json:
            logo_info = cat_json['consistency_tracking'].get('logo_placement', {})
            print(f"  Logo: {logo_info.get('consistency_score', 'Unknown')}")

        # Print design system canvas info if available
        if 'design_system' in cat_json and 'canvas' in cat_json['design_system']:
            canvas = cat_json['design_system']['canvas']
            print(f"  Canvas: {canvas.get('width', '?')}x{canvas.get('height', '?')}")

        print()

    # Print universal elements if available
    has_universal = False
    print("Universal Elements (shared across all categories):")
    print("-" * 60)

    if 'canvas' in main_json:
        canvas = main_json['canvas']
        print(f"  Canvas: {canvas.get('width', 0)}x{canvas.get('height', 0)}")
        has_universal = True

    if 'fonts' in main_json:
        fonts = main_json['fonts']
        print(f"  Fonts: {', '.join(fonts)}")
        has_universal = True

    if 'logo_position' in main_json:
        print(f"  Logo: Always {main_json['logo_position']}")
        has_universal = True

    if 'brand_colors' in main_json:
        colors = main_json['brand_colors']
        print(f"  Brand Colors: {len(colors)} colors")
        for color in colors[:3]:  # Show first 3
            print(f"    - {color.get('name', 'Unknown')} ({color.get('hex', 'N/A')})")
        has_universal = True

    if not has_universal:
        print("  No consistent universal elements detected")

    print()

    print()
    print("All done!")


if __name__ == "__main__":
    main()
