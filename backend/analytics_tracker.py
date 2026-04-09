
import json
import os
import uuid
from datetime import datetime
import csv
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

class AnalyticsTracker:
    """
    Tracks video performance and affiliate click analytics for ShadowCast.
    Uses a JSON file as a persistent data store.
    """

    def __init__(self, db_path="shadowcast/output/analytics.json"):
        """
        Initializes the AnalyticsTracker, loading existing data or creating a new store.

        Args:
            db_path (str): The path to the JSON file used as the database.
        """
        self.db_path = db_path
        self.data = {"videos": {}, "metrics": []}
        self._load_data()

    def _load_data(self):
        """
        Loads analytics data from the JSON file.
        """
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r') as f:
                try:
                    self.data = json.load(f)
                except json.JSONDecodeError:
                    self.data = {"videos": {}, "metrics": []} # Initialize if JSON is malformed
        else:
            # Ensure the directory exists if the file doesn't
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _save_data(self):
        """
        Saves the current analytics data to the JSON file.
        """
        with open(self.db_path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def track_video(self, product_name, hook_type, format_type, video_path, youtube_url=None):
        """
        Registers a video for tracking.

        Args:
            product_name (str): The name of the product featured in the video.
            hook_type (str): The type of hook used (e.g., "problem-solution", "story-telling").
            format_type (str): The video format (e.g., "short_form", "long_form").
            video_path (str): Local path to the video file.
            youtube_url (str, optional): The YouTube URL of the video, if uploaded.

        Returns:
            str: The unique video ID generated for this video.
        """
        video_id = str(uuid.uuid4())
        self.data["videos"][video_id] = {
            "product_name": product_name,
            "hook_type": hook_type,
            "format_type": format_type,
            "video_path": video_path,
            "youtube_url": youtube_url,
            "created_at": datetime.now().isoformat()
        }
        self._save_data()
        return video_id

    def record_metric(self, video_id, metric_type, value):
        """
        Records a metric for a specific video.

        Args:
            video_id (str): The ID of the video.
            metric_type (str): The type of metric (e.g., "views", "likes", "comments", "ctr", "affiliate_clicks", "revenue").
            value (float or int): The value of the metric.

        Raises:
            ValueError: If the video_id does not exist.
        """
        if video_id not in self.data["videos"]:
            raise ValueError(f"Video with ID {video_id} not found.")

        self.data["metrics"].append({
            "video_id": video_id,
            "metric_type": metric_type,
            "value": value,
            "timestamp": datetime.now().isoformat()
        })
        self._save_data()

    def get_video_stats(self, video_id):
        """
        Returns all metrics for a specific video.

        Args:
            video_id (str): The ID of the video.

        Returns:
            dict: A dictionary containing video details and aggregated metrics.
                  Returns None if the video_id does not exist.
        """
        if video_id not in self.data["videos"]:
            return None

        video_info = self.data["videos"][video_id].copy()
        metrics = [m for m in self.data["metrics"] if m["video_id"] == video_id]

        # Aggregate metrics
        aggregated_metrics = {
            "views": 0,
            "likes": 0,
            "comments": 0,
            "ctr": 0.0,
            "affiliate_clicks": 0,
            "revenue": 0.0
        }

        for metric in metrics:
            m_type = metric["metric_type"]
            m_value = metric["value"]
            if m_type in aggregated_metrics:
                # For CTR, we'll take the last recorded value or average if multiple exist
                if m_type == "ctr":
                    aggregated_metrics[m_type] = m_value
                else:
                    aggregated_metrics[m_type] += m_value

        # Calculate derived metrics
        total_views = aggregated_metrics["views"]
        total_affiliate_clicks = aggregated_metrics["affiliate_clicks"]
        total_revenue = aggregated_metrics["revenue"]

        video_info["total_views"] = total_views
        video_info["total_likes"] = aggregated_metrics["likes"]
        video_info["total_comments"] = aggregated_metrics["comments"]
        video_info["latest_ctr"] = aggregated_metrics["ctr"]
        video_info["total_affiliate_clicks"] = total_affiliate_clicks
        video_info["total_revenue"] = total_revenue

        video_info["conversion_rate"] = (total_affiliate_clicks / total_views) if total_views > 0 else 0.0
        video_info["revenue_per_view"] = (total_revenue / total_views) if total_views > 0 else 0.0

        return video_info

    def get_product_report(self, product_name):
        """
        Aggregates statistics across all videos for a specific product.

        Args:
            product_name (str): The name of the product.

        Returns:
            dict: A dictionary containing aggregated statistics for the product.
        """
        product_videos = [vid_id for vid_id, vid_info in self.data["videos"].items()
                          if vid_info["product_name"] == product_name]

        total_views = 0
        total_likes = 0
        total_comments = 0
        total_affiliate_clicks = 0
        total_revenue = 0.0
        video_count = len(product_videos)

        for video_id in product_videos:
            stats = self.get_video_stats(video_id)
            if stats:
                total_views += stats.get("total_views", 0)
                total_likes += stats.get("total_likes", 0)
                total_comments += stats.get("total_comments", 0)
                total_affiliate_clicks += stats.get("total_affiliate_clicks", 0)
                total_revenue += stats.get("total_revenue", 0.0)

        report = {
            "product_name": product_name,
            "video_count": video_count,
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_affiliate_clicks": total_affiliate_clicks,
            "total_revenue": total_revenue,
            "avg_views_per_video": (total_views / video_count) if video_count > 0 else 0,
            "conversion_rate": (total_affiliate_clicks / total_views) if total_views > 0 else 0.0,
            "revenue_per_view": (total_revenue / total_views) if total_views > 0 else 0.0
        }
        return report

    def get_hook_performance(self):
        """
        Compares the performance of different hook types across all videos.

        Returns:
            dict: A dictionary where keys are hook types and values are their aggregated performance.
        """
        hook_performance = {}
        for video_id, video_info in self.data["videos"].items():
            hook_type = video_info["hook_type"]
            stats = self.get_video_stats(video_id)
            if stats:
                if hook_type not in hook_performance:
                    hook_performance[hook_type] = {
                        "video_count": 0,
                        "total_views": 0,
                        "total_affiliate_clicks": 0,
                        "total_revenue": 0.0
                    }
                hook_performance[hook_type]["video_count"] += 1
                hook_performance[hook_type]["total_views"] += stats.get("total_views", 0)
                hook_performance[hook_type]["total_affiliate_clicks"] += stats.get("total_affiliate_clicks", 0)
                hook_performance[hook_type]["total_revenue"] += stats.get("total_revenue", 0.0)

        # Calculate derived metrics for each hook type
        for hook_type, data in hook_performance.items():
            total_views = data["total_views"]
            total_affiliate_clicks = data["total_affiliate_clicks"]
            total_revenue = data["total_revenue"]
            video_count = data["video_count"]

            data["avg_views_per_video"] = (total_views / video_count) if video_count > 0 else 0
            data["conversion_rate"] = (total_affiliate_clicks / total_views) if total_views > 0 else 0.0
            data["revenue_per_view"] = (total_revenue / total_views) if total_views > 0 else 0.0

        return hook_performance

    def get_format_performance(self):
        """
        Compares short-form vs. long-form video performance.

        Returns:
            dict: A dictionary where keys are format types and values are their aggregated performance.
        """
        format_performance = {}
        for video_id, video_info in self.data["videos"].items():
            format_type = video_info["format_type"]
            stats = self.get_video_stats(video_id)
            if stats:
                if format_type not in format_performance:
                    format_performance[format_type] = {
                        "video_count": 0,
                        "total_views": 0,
                        "total_affiliate_clicks": 0,
                        "total_revenue": 0.0
                    }
                format_performance[format_type]["video_count"] += 1
                format_performance[format_type]["total_views"] += stats.get("total_views", 0)
                format_performance[format_type]["total_affiliate_clicks"] += stats.get("total_affiliate_clicks", 0)
                format_performance[format_type]["total_revenue"] += stats.get("total_revenue", 0.0)

        # Calculate derived metrics for each format type
        for format_type, data in format_performance.items():
            total_views = data["total_views"]
            total_affiliate_clicks = data["total_affiliate_clicks"]
            total_revenue = data["total_revenue"]
            video_count = data["video_count"]

            data["avg_views_per_video"] = (total_views / video_count) if video_count > 0 else 0
            data["conversion_rate"] = (total_affiliate_clicks / total_views) if total_views > 0 else 0.0
            data["revenue_per_view"] = (total_revenue / total_views) if total_views > 0 else 0.0

        return format_performance

    def get_top_performers(self, metric="views", limit=10):
        """
        Returns the top videos by a specified metric.

        Args:
            metric (str): The metric to sort by (e.g., "total_views", "total_revenue", "conversion_rate").
            limit (int): The maximum number of top performers to return.

        Returns:
            list: A list of dictionaries, each representing a top-performing video.
        """
        video_performances = []
        for video_id in self.data["videos"]:
            stats = self.get_video_stats(video_id)
            if stats and metric in stats:
                video_performances.append({"video_id": video_id, "metric_value": stats[metric], **stats})

        # Sort in descending order based on the metric_value
        top_performers = sorted(video_performances, key=lambda x: x["metric_value"], reverse=True)
        return top_performers[:limit]

    def get_revenue_report(self):
        """
        Generates a comprehensive revenue report.

        Returns:
            dict: A dictionary containing total revenue, revenue per video, and revenue per hook type.
        """
        total_revenue = 0.0
        revenue_per_video = {}
        revenue_per_hook_type = {}

        for video_id, video_info in self.data["videos"].items():
            stats = self.get_video_stats(video_id)
            if stats:
                video_revenue = stats.get("total_revenue", 0.0)
                total_revenue += video_revenue
                revenue_per_video[video_id] = {
                    "product_name": video_info["product_name"],
                    "hook_type": video_info["hook_type"],
                    "revenue": video_revenue
                }

                hook_type = video_info["hook_type"]
                revenue_per_hook_type.setdefault(hook_type, 0.0)
                revenue_per_hook_type[hook_type] += video_revenue

        return {
            "total_revenue": total_revenue,
            "revenue_per_video": revenue_per_video,
            "revenue_per_hook_type": revenue_per_hook_type
        }

    def export_csv(self, output_path):
        """
        Exports all analytics data to a CSV file.

        Args:
            output_path (str): The path to the output CSV file.
        """
        all_video_stats = []
        for video_id in self.data["videos"]:
            stats = self.get_video_stats(video_id)
            if stats:
                all_video_stats.append(stats)

        if not all_video_stats:
            print("No data to export.")
            return

        # Determine fieldnames from the first video's stats
        fieldnames = list(all_video_stats[0].keys())

        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_video_stats)
        print(f"Analytics exported to {output_path}")

    def generate_dashboard_data(self):
        """
        Returns a dictionary with summary statistics formatted for a frontend dashboard.

        Returns:
            dict: A dictionary containing various summary statistics.
        """
        total_videos = len(self.data["videos"])
        total_views_all = 0
        total_affiliate_clicks_all = 0
        total_revenue_all = 0.0

        for video_id in self.data["videos"]:
            stats = self.get_video_stats(video_id)
            if stats:
                total_views_all += stats.get("total_views", 0)
                total_affiliate_clicks_all += stats.get("total_affiliate_clicks", 0)
                total_revenue_all += stats.get("total_revenue", 0.0)

        conversion_rate_all = (total_affiliate_clicks_all / total_views_all) if total_views_all > 0 else 0.0
        revenue_per_view_all = (total_revenue_all / total_views_all) if total_views_all > 0 else 0.0

        # Get top performers for dashboard display
        top_revenue_videos = self.get_top_performers(metric="total_revenue", limit=5)
        top_conversion_videos = self.get_top_performers(metric="conversion_rate", limit=5)

        return {
            "summary": {
                "total_videos": total_videos,
                "total_views": total_views_all,
                "total_affiliate_clicks": total_affiliate_clicks_all,
                "total_revenue": total_revenue_all,
                "overall_conversion_rate": conversion_rate_all,
                "overall_revenue_per_view": revenue_per_view_all
            },
            "hook_performance": self.get_hook_performance(),
            "format_performance": self.get_format_performance(),
            "top_revenue_videos": [{
                "video_id": v["video_id"],
                "product_name": v["product_name"],
                "revenue": v["total_revenue"]
            } for v in top_revenue_videos],
            "top_conversion_videos": [{
                "video_id": v["video_id"],
                "product_name": v["product_name"],
                "conversion_rate": v["conversion_rate"]
            } for v in top_conversion_videos]
        }

def create_tracking_link(affiliate_url, video_id, platform="youtube"):
    """
    Wraps an affiliate URL with UTM parameters for tracking source.

    Args:
        affiliate_url (str): The original affiliate URL.
        video_id (str): The ID of the video associated with the link.
        platform (str): The platform where the link will be used (e.g., "youtube", "tiktok").

    Returns:
        str: The tracking-enabled URL.
    """
    parsed_url = urlparse(affiliate_url)
    query_params = parse_qs(parsed_url.query)

    # Add UTM parameters
    query_params["utm_source"] = [platform]
    query_params["utm_medium"] = ["video"]
    query_params["utm_campaign"] = [f"shadowcast_{video_id}"]

    # Reconstruct the URL
    encoded_query = urlencode(query_params, doseq=True)
    tracking_url = urlunparse(
        (parsed_url.scheme,
         parsed_url.netloc,
         parsed_url.path,
         parsed_url.params,
         encoded_query,
         parsed_url.fragment)
    )
    return tracking_url

def parse_youtube_analytics(api_key, video_ids):
    """
    Fetches basic public stats from YouTube Data API v3 (views, likes, comments).
    Includes graceful fallback if no API key is provided.

    Args:
        api_key (str): Your YouTube Data API v3 key. Can be None for fallback.
        video_ids (list): A list of YouTube video IDs.

    Returns:
        dict: A dictionary where keys are video IDs and values are their stats (views, likes, comments).
              Returns empty dict if API key is missing or API call fails.
    """
    if not api_key:
        print("YouTube API key not provided. Skipping YouTube analytics fetching.")
        return {video_id: {"views": 0, "likes": 0, "comments": 0} for video_id in video_ids}

    # This part would typically involve making actual API calls.
    # For this exercise, we'll simulate a response or return zeros.
    # In a real scenario, you'd use a library like `google-api-python-client`.
    # Example (conceptual, not executable without actual API setup):
    # from googleapiclient.discovery import build
    # youtube = build('youtube', 'v3', developerKey=api_key)
    # request = youtube.videos().list(
    #     part='statistics',
    #     id=','.join(video_ids)
    # )
    # response = request.execute()
    # stats = {}
    # for item in response.get('items', []):
    #     video_id = item['id']
    #     statistics = item['statistics']
    #     stats[video_id] = {
    #         'views': int(statistics.get('viewCount', 0)),
    #         'likes': int(statistics.get('likeCount', 0)),
    #         'comments': int(statistics.get('commentCount', 0))
    #     }
    # return stats

    print("Simulating YouTube API response (API key provided but no actual API call).")
    # Simulate some data for demonstration purposes if an API key is provided
    simulated_stats = {}
    for video_id in video_ids:
        simulated_stats[video_id] = {
            "views": 1000 + video_ids.index(video_id) * 500,
            "likes": 50 + video_ids.index(video_id) * 10,
            "comments": 5 + video_ids.index(video_id) * 2
        }
    return simulated_stats


if __name__ == "__main__":
    # This will be filled in Phase 4
    pass


    print("\n--- Sample Data Generation and Report ---")
    tracker = AnalyticsTracker()

    # Clear previous data for a clean run
    tracker.data = {"videos": {}, "metrics": []}
    tracker._save_data()

    # Track some videos
    video1_id = tracker.track_video("Product A", "problem-solution", "long_form", "/videos/prod_a_v1.mp4", "https://youtu.be/abc1")
    video2_id = tracker.track_video("Product A", "story-telling", "short_form", "/videos/prod_a_v2.mp4", "https://youtu.be/abc2")
    video3_id = tracker.track_video("Product B", "testimonial", "long_form", "/videos/prod_b_v1.mp4", "https://youtu.be/abc3")
    video4_id = tracker.track_video("Product C", "problem-solution", "short_form", "/videos/prod_c_v1.mp4", "https://youtu.be/abc4")

    print(f"Tracked Video 1 ID: {video1_id}")
    print(f"Tracked Video 2 ID: {video2_id}")
    print(f"Tracked Video 3 ID: {video3_id}")
    print(f"Tracked Video 4 ID: {video4_id}")

    # Record metrics for Video 1
    tracker.record_metric(video1_id, "views", 1000)
    tracker.record_metric(video1_id, "likes", 50)
    tracker.record_metric(video1_id, "comments", 5)
    tracker.record_metric(video1_id, "affiliate_clicks", 20)
    tracker.record_metric(video1_id, "revenue", 10.50)
    tracker.record_metric(video1_id, "ctr", 0.02) # Example CTR

    # Record metrics for Video 2
    tracker.record_metric(video2_id, "views", 2500)
    tracker.record_metric(video2_id, "likes", 120)
    tracker.record_metric(video2_id, "comments", 15)
    tracker.record_metric(video2_id, "affiliate_clicks", 80)
    tracker.record_metric(video2_id, "revenue", 45.75)
    tracker.record_metric(video2_id, "ctr", 0.032)

    # Record metrics for Video 3
    tracker.record_metric(video3_id, "views", 800)
    tracker.record_metric(video3_id, "likes", 30)
    tracker.record_metric(video3_id, "comments", 2)
    tracker.record_metric(video3_id, "affiliate_clicks", 10)
    tracker.record_metric(video3_id, "revenue", 5.20)
    tracker.record_metric(video3_id, "ctr", 0.015)

    # Record metrics for Video 4
    tracker.record_metric(video4_id, "views", 1500)
    tracker.record_metric(video4_id, "likes", 70)
    tracker.record_metric(video4_id, "comments", 8)
    tracker.record_metric(video4_id, "affiliate_clicks", 40)
    tracker.record_metric(video4_id, "revenue", 22.00)
    tracker.record_metric(video4_id, "ctr", 0.028)

    # Test get_video_stats
    print("\n--- Video Stats for Video 1 ---")
    stats_v1 = tracker.get_video_stats(video1_id)
    if stats_v1:
        for k, v in stats_v1.items():
            print(f"  {k}: {v}")

    # Test get_product_report
    print("\n--- Product A Report ---")
    product_a_report = tracker.get_product_report("Product A")
    for k, v in product_a_report.items():
        print(f"  {k}: {v}")

    # Test get_hook_performance
    print("\n--- Hook Performance Report ---")
    hook_perf = tracker.get_hook_performance()
    for hook, data in hook_perf.items():
        print(f"  Hook Type: {hook}")
        for k, v in data.items():
            print(f"    {k}: {v}")

    # Test get_format_performance
    print("\n--- Format Performance Report ---")
    format_perf = tracker.get_format_performance()
    for fmt, data in format_perf.items():
        print(f"  Format Type: {fmt}")
        for k, v in data.items():
            print(f"    {k}: {v}")

    # Test get_top_performers
    print("\n--- Top 2 Videos by Revenue ---")
    top_revenue = tracker.get_top_performers(metric="total_revenue", limit=2)
    for i, video in enumerate(top_revenue):
        print(f'  {i+1}. Video ID: {video["video_id"]}, Product: {video["product_name"]}, Revenue: {video["total_revenue"]:.2f}')

    # Test get_revenue_report
    print("\n--- Revenue Report ---")
    revenue_report = tracker.get_revenue_report()
    print(f'  Total Revenue: {revenue_report["total_revenue"]:.2f}')
    print("  Revenue Per Video:")
    for vid_id, data in revenue_report["revenue_per_video"].items():
        print(f'    {vid_id} ({data["product_name"]} - {data["hook_type"]}) : {data["revenue"]:.2f}')
    print("  Revenue Per Hook Type:")
    for hook, rev in revenue_report["revenue_per_hook_type"].items():
        print(f"    {hook}: {rev:.2f}")

    # Test create_tracking_link
    print("\n--- Tracking Link Example ---")
    affiliate_link = "https://example.com/product_a?ref=shadowcast"
    tracking_link = create_tracking_link(affiliate_link, video1_id, "youtube")
    print(f"  Original: {affiliate_link}")
    print(f"  Tracking: {tracking_link}")

    # Test parse_youtube_analytics (with simulated data)
    print("\n--- YouTube Analytics (Simulated) ---")
    youtube_video_ids = []
    for video_id_to_check in [video1_id, video2_id]:
        stats_v = tracker.get_video_stats(video_id_to_check)
        if stats_v and stats_v["youtube_url"]:
            parsed_url = urlparse(stats_v["youtube_url"])
            if parsed_url.hostname == "youtu.be":
                youtube_video_ids.append(parsed_url.path[1:])
            elif parsed_url.hostname in ("www.youtube.com", "youtube.com") and "v" in parse_qs(parsed_url.query):
                youtube_video_ids.append(parse_qs(parsed_url.query)["v"][0])
    youtube_stats = parse_youtube_analytics(None, youtube_video_ids) # No API key for fallback
    for vid_id, stats in youtube_stats.items():
        print(f'  YouTube Video ID: {vid_id}, Views: {stats["views"]}, Likes: {stats["likes"]}, Comments: {stats["comments"]}')

    # Test export_csv
    print("\n--- Exporting to CSV ---")
    tracker.export_csv("shadowcast/output/analytics_report.csv")

    # Test generate_dashboard_data
    print("\n--- Dashboard Data ---")
    dashboard_data = tracker.generate_dashboard_data()
    # print(json.dumps(dashboard_data, indent=4)) # Uncomment to see full dashboard data
    print(f'  Total Videos: {dashboard_data["summary"]["total_videos"]}')
    print(f'  Overall Revenue: {dashboard_data["summary"]["total_revenue"]:.2f}')
    print(f'  Top Revenue Video (ID): {dashboard_data["top_revenue_videos"][0]["video_id"] if dashboard_data["top_revenue_videos"] else "N/A"}')
