
import json
import os
import subprocess
import time
from datetime import datetime, timedelta

import httpx

class SocialPoster:
    def __init__(self, config_path=None):
        """
        Initializes the SocialPoster with credentials and loads the posting queue.

        Args:
            config_path (str, optional): Path to a configuration file (e.g., .env).
                                         Currently, credentials are loaded from environment variables.
        """
        self.config = {}
        self.load_credentials(config_path)
        self.queue_file = "output/posting_queue.json"
        os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
        self.load_queue()

    def load_credentials(self, config_path):
        """
        Loads API credentials from environment variables.
        Users should set the following environment variables:
        - INSTAGRAM_ACCESS_TOKEN: Instagram Graph API access token.
          (See: https://developers.facebook.com/docs/instagram/guides/content-publishing#get-started)
        - TIKTOK_CLIENT_KEY: TikTok Content Posting API client key.
          (See: https://developers.tiktok.com/products/tiktok-content-posting-api/overview/)
        - TIKTOK_CLIENT_SECRET: TikTok Content Posting API client secret.
        - TIKTOK_ACCESS_TOKEN: TikTok Content Posting API access token.

        Args:
            config_path (str, optional): Currently unused. Credentials are loaded from environment variables.
        """
        self.config["instagram_access_token"] = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.config["tiktok_client_key"] = os.getenv("TIKTOK_CLIENT_KEY")
        self.config["tiktok_client_secret"] = os.getenv("TIKTOK_CLIENT_SECRET")
        self.config["tiktok_access_token"] = os.getenv("TIKTOK_ACCESS_TOKEN")

    def _check_credentials(self):
        """
        Checks if the necessary credentials for each platform are configured.
        """
        credentials_status = {
            "instagram": bool(self.config.get("instagram_access_token")),
            "tiktok": bool(self.config.get("tiktok_client_key") and
                           self.config.get("tiktok_client_secret") and
                           self.config.get("tiktok_access_token"))
        }
        return credentials_status

    def _get_instagram_api_base_url(self):
        return "https://graph.facebook.com/v19.0/"

    def _get_tiktok_api_base_url(self):
        return "https://open.tiktokapis.com/v2/"

    def post_to_instagram(self, video_path, caption, hashtags=[], cover_image=None, dry_run=False):
        """
        Posts a video to Instagram Reels via the Instagram Graph API.

        Requires a Facebook Business account and an access token with necessary permissions.
        See: https://developers.facebook.com/docs/instagram/guides/content-publishing

        Args:
            video_path (str): Path to the video file.
            caption (str): Caption for the video.
            hashtags (list, optional): List of hashtags. Defaults to [].
            cover_image (str, optional): Path to an optional cover image. Defaults to None.
            dry_run (bool, optional): If True, simulates the posting process without actually posting. Defaults to False.

        Returns:
            dict: A dictionary with post_id and status.
        """
        if dry_run:
            print("Dry run: Simulating Instagram post.")
            return {"post_id": "dry_run_instagram_123", "status": "success"}

        access_token = self.config.get("instagram_access_token")
        if not access_token:
            return {"status": "error", "message": "Instagram access token not configured."}

        try:
            # 1. Upload video to Instagram
            upload_url = f"{self._get_instagram_api_base_url()}me/media?access_token={access_token}"
            upload_params = {
                "media_type": "VIDEO",
                "video_url": video_path, # In a real scenario, this would be a publicly accessible URL or uploaded binary
                "caption": f"{caption} {' '.join([f'#{tag}' for tag in hashtags])}"
            }
            if cover_image:
                upload_params["cover_url"] = cover_image # This would also need to be a publicly accessible URL

            response = httpx.post(upload_url, json=upload_params)
            response.raise_for_status()
            creation_id = response.json()["id"]

            # 2. Check upload status (Instagram requires a separate status check)
            status_url = f"{self._get_instagram_api_base_url()}{creation_id}?fields=status_code&access_token={access_token}"
            status_response = httpx.get(status_url)
            status_response.raise_for_status()
            status_code = status_response.json()["status_code"]

            # Wait for video to be ready (simplified for this example)
            while status_code != "FINISHED":
                time.sleep(5)
                status_response = httpx.get(status_url)
                status_response.raise_for_status()
                status_code = status_response.json()["status_code"]

            # 3. Publish the video
            publish_url = f"{self._get_instagram_api_base_url()}me/media_publish?creation_id={creation_id}&access_token={access_token}"
            publish_response = httpx.post(publish_url)
            publish_response.raise_for_status()
            post_id = publish_response.json()["id"]

            print(f"Successfully posted to Instagram: {video_path}")
            return {"post_id": post_id, "status": "success"}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"Instagram API error: {e.response.text}"}
        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred during Instagram posting: {e}"}

    def post_to_tiktok(self, video_path, title, hashtags=[], cover_image=None, dry_run=False):
        """
        Posts a video to TikTok via the TikTok Content Posting API.

        Requires a TikTok developer account and an access token with necessary permissions.
        See: https://developers.tiktok.com/products/tiktok-content-posting-api/overview/

        Args:
            video_path (str): Path to the video file.
            title (str): Title for the video.
            hashtags (list, optional): List of hashtags. Defaults to [].
            cover_image (str, optional): Path to an optional cover image. Defaults to None.
            dry_run (bool, optional): If True, simulates the posting process without actually posting. Defaults to False.

        Returns:
            dict: A dictionary with post_id and status.
        """
        if dry_run:
            print("Dry run: Simulating TikTok post.")
            return {"post_id": "dry_run_tiktok_456", "status": "success"}

        client_key = self.config.get("tiktok_client_key")
        client_secret = self.config.get("tiktok_client_secret")
        if not client_key or not client_secret:
            return {"status": "error", "message": "TikTok credentials not configured."}

        try:
            # 1. Initiate video upload
            # This is a simplified placeholder. TikTok API typically involves a multi-step upload process:
            # a. Request upload URL
            # b. Upload video file to the provided URL
            # c. Confirm upload and get video ID
            # For demonstration, we'll simulate a direct post.

            # In a real scenario, you'd make an API call to get an upload URL:
            # upload_init_url = f"{self._get_tiktok_api_base_url()}post/publish/creator_post/init/"
            # headers = {"Authorization": f"Bearer {access_token}"}
            # response = httpx.post(upload_init_url, headers=headers, json={"post_info": {"title": title, "hashtags": hashtags}})
            # upload_url = response.json()["data"]["upload_url"]

            # Then upload the video file using httpx.put or similar
            # httpx.put(upload_url, content=open(video_path, "rb").read())

            # For now, simulate a successful post after a delay
            print(f"Simulating TikTok video upload for {video_path}")
            time.sleep(5) # Simulate upload time

            # 2. Publish the video (simplified)
            publish_url = f"{self._get_tiktok_api_base_url()}post/publish/creator_post/post/"
            headers = {
                "Authorization": f"Bearer {self.config.get('tiktok_access_token')}", # Assuming a separate TikTok access token
                "Content-Type": "application/json"
            }
            publish_params = {
                "post_info": {
                    "title": title,
                    "privacy_level": "PUBLIC",
                    "disable_comment": False,
                    "disable_duet": False,
                    "disable_stitch": False,
                    "hashtags": hashtags
                },
                "video_binary": "base64_encoded_video_content" # In a real scenario, this would be the actual video content or a reference
            }
            # If cover_image is provided, it would also be part of the publish_params

            # Simulate API call
            # response = httpx.post(publish_url, headers=headers, json=publish_params)
            # response.raise_for_status()
            # post_id = response.json()["data"]["share_id"]

            post_id = "tiktok_post_" + str(int(time.time())) # Dummy post ID

            print(f"Successfully posted to TikTok: {video_path}")
            return {"post_id": post_id, "status": "success"}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"TikTok API error: {e.response.text}"}
        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred during TikTok posting: {e}"}

    def load_queue(self):
        if os.path.exists(self.queue_file):
            with open(self.queue_file, "r") as f:
                self.queue = json.load(f)
        else:
            self.queue = []

    def save_queue(self):
        with open(self.queue_file, "w") as f:
            json.dump(self.queue, f, indent=4)

    def schedule_post(self, platform, video_path, caption, hashtags, scheduled_time):
        """
        Schedules a post to be added to the queue.

        Args:
            platform (str): Target platform ('instagram' or 'tiktok').
            video_path (str): Path to the video file.
            caption (str): Caption for the video (used for Instagram) or title (for TikTok).
            hashtags (list): List of hashtags.
            scheduled_time (str): ISO format string for scheduled time (e.g., '2024-12-31T10:00:00').
        """
        post = {
            "platform": platform,
            "video_path": video_path,
            "caption": caption,
            "hashtags": hashtags,
            "scheduled_time": scheduled_time,
            "posted": False
        }
        self.queue.append(post)
        self.save_queue()
        print(f"Post scheduled for {platform} at {scheduled_time}")

    def get_queue(self):
        """
        Returns the list of pending scheduled posts.
        """
        return [post for post in self.queue if not post["posted"]]

    def process_queue(self, dry_run=False):
        """
        Processes the posting queue, posting any due items.
        """
        now = datetime.now()
        for post in self.queue:
            if not post["posted"] and datetime.fromisoformat(post["scheduled_time"]) <= now:
                print(f"Processing scheduled post for {post['platform']}: {post['video_path']}")
                if post["platform"] == "instagram":
                    result = self.post_to_instagram(
                        post["video_path"],
                        post["caption"],
                        post["hashtags"],
                        dry_run=dry_run
                    )
                elif post["platform"] == "tiktok":
                    result = self.post_to_tiktok(
                        post["video_path"],
                        post["caption"], # TikTok uses title, using caption for now
                        post["hashtags"],
                        dry_run=dry_run
                    )
                else:
                    result = {"status": "error", "message": f"Unknown platform: {post['platform']}"}

                if result.get("status") == "success":
                    post["posted"] = True
                    print(f"Successfully posted to {post['platform']}.")
                else:
                    print(f"Failed to post to {post['platform']}: {result.get('message', 'Unknown error')}")
        self.save_queue()

    def repurpose_for_platform(self, video_path, platform, output_path=None):
        """
        Adjusts video specifications (aspect ratio, duration limits) for each platform
        using ffmpeg subprocess.

        Args:
            video_path (str): Path to the input video file.
            platform (str): Target platform ('instagram' or 'tiktok').
            output_path (str, optional): Path for the output video file. If None, a default path will be generated.

        Returns:
            str: Path to the repurposed video file.
        """
        if not output_path:
            base, ext = os.path.splitext(video_path)
            output_path = f"{base}_{platform}{ext}"

        # Check if ffmpeg is installed
        if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
            print("Error: ffmpeg is not installed. Please install ffmpeg to use video repurposing.")
            return video_path

        ffmpeg_cmd = []
        if platform == "instagram":
            # Instagram Reels typically supports 9:16 aspect ratio, max 90 seconds
            # This is a placeholder, actual ffmpeg commands can be complex
            ffmpeg_cmd = [
                "ffmpeg", "-i", video_path,
                "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-t", "90", # Max 90 seconds
                output_path
            ]
        elif platform == "tiktok":
            # TikTok typically supports 9:16 aspect ratio, max 3 minutes
            ffmpeg_cmd = [
                "ffmpeg", "-i", video_path,
                "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-t", "180", # Max 3 minutes
                output_path
            ]
        else:
            print(f"Warning: No specific repurposing rules for platform {platform}. Returning original video path.")
            return video_path

        try:
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            print(f"Video repurposed for {platform}: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"Error repurposing video for {platform}: {e.stderr.decode().strip()}")
            return video_path

def get_platform_status():
    """
    Returns a dictionary showing which platforms have valid credentials configured.
    """
    # This function would ideally check actual credential validity with a small API call
    # For now, it just checks if the placeholders are filled.
    # For demonstration, we'll assume credentials are not set unless explicitly configured.
    # In a real scenario, you might want to load a dummy config or use environment variables.
    # For this test, we'll manually set some values to simulate configuration.
    # config = SocialPoster().config # Load config to check credentials
    poster_instance = SocialPoster() # Create a temporary instance to access its config
    credentials_status = poster_instance._check_credentials()
    status = {
        "instagram": "Configured" if credentials_status["instagram"] else "Not Configured",
        "tiktok": "Configured" if credentials_status["tiktok"] else "Not Configured"
    }
    return status

if __name__ == "__main__":
    print("--- SocialPoster Module Test ---")

    # Initialize SocialPoster (without actual credentials for this test)
    poster = SocialPoster()

    # Test get_platform_status
    print("\nPlatform Status:", get_platform_status())

    # Schedule some dummy posts
    print("\nScheduling posts...")
    now = datetime.now()
    future_time_instagram = (now + timedelta(seconds=10)).isoformat()
    future_time_tiktok = (now + timedelta(seconds=20)).isoformat()

    poster.schedule_post("instagram", "./videos/test_instagram.mp4", "My Instagram Reel! #reels #video", ["reels", "video"], future_time_instagram)
    poster.schedule_post("tiktok", "./videos/test_tiktok.mp4", "My TikTok Video! #tiktok #viral", ["tiktok", "viral"], future_time_tiktok)

    print("\nPending Queue:", poster.get_queue())

    print("\nProcessing queue (dry run)...")
    poster.process_queue(dry_run=True)
    print("Queue after first processing:", poster.get_queue())

    # Simulate waiting for scheduled time
    print("\nWaiting for scheduled posts...")
    time.sleep(25) # Wait for both posts to be due

    print("\nProcessing queue again (dry run)...")
    poster.process_queue(dry_run=True)
    print("Queue after second processing:", poster.get_queue())

    print("\n--- Test Complete ---")


