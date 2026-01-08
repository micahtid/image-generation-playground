import json
from datetime import datetime

from apify_scraper import scrape_instagram_posts
from gemini_analyzer import analyze_posts_with_gemini
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
    """Clear only design_analysis files, keep raw_posts."""
    if OUTPUT_DIR.exists():
        for file in OUTPUT_DIR.iterdir():
            if file.is_file() and file.name.startswith("design_analysis_"):
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

    # Step 2: Analyze with Gemini
    print("STEP 2: Analyzing design patterns with Gemini...")
    print("-" * 60)
    try:
        analysis = analyze_posts_with_gemini(posts)
        print("Analysis complete")
    except Exception as e:
        print(f"Error analyzing posts: {e}")
        return

    # Step 3: Save analysis
    print()
    print("STEP 3: Saving analysis results...")
    print("-" * 60)
    analysis_file = OUTPUT_DIR / f"design_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(f"Design analysis saved to: {analysis_file}")

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
    print(f"Analysis: {analysis_file}")
    print()

    # Print a preview of the analysis
    if isinstance(analysis, dict):
        if 'design_system' in analysis:
            ds = analysis['design_system']
            print("Design System Summary:")
            print("-" * 60)
            if 'canvas' in ds:
                print(f"  Canvas: {ds['canvas'].get('width', '?')}x{ds['canvas'].get('height', '?')} ({ds['canvas'].get('aspect_ratio', '?')})")
            if 'colors' in ds:
                colors = ds['colors']
                print(f"  Colors:")
                for name, color in colors.items():
                    if isinstance(color, dict):
                        print(f"    {name}: {color.get('name', '?')} ({color.get('hex', '?')})")
            if 'typography' in ds and 'headline' in ds['typography']:
                print(f"  Headline Font: {ds['typography']['headline'].get('font_family', '?')}")

        if 'prompt_template' in analysis:
            print()
            print("Prompt Template:")
            print("-" * 60)
            print(analysis['prompt_template'])

        if 'generation_instructions' in analysis:
            gi = analysis['generation_instructions']
            if 'forbidden' in gi:
                print()
                print("Forbidden (will NOT appear in generated images):")
                for item in gi['forbidden'][:3]:
                    print(f"  - {item}")

    print()
    print("All done!")


if __name__ == "__main__":
    main()
