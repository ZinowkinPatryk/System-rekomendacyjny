import os
import time
import requests
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv




class DataCollector:
    def __init__(self, limit):
        load_dotenv()
        self.dataset = os.getenv("DATASET_PATH")
        self.api_key = os.getenv("API_KEY")
        self.games_information = []
        self.users_information = []
        self.recommendations = []
        self.games_id = self.get_app_ids(self.dataset, limit)

    @staticmethod
    def get_app_ids(path, limit):
        try:
            df = pd.read_csv(path)
            games_id = df.iloc[:, 0].tolist()
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        return games_id[:limit]

    def get_games_data(self):
        for app_id in tqdm(self.games_id, desc="Pobieranie danych gier", unit="gry"):
            url_steam = "https://store.steampowered.com/api/appdetails"
            url_steam_spy = "https://steamspy.com/api.php"
            metadata = {
                "app_id": app_id,
                "name": None,
                "platforms": [],
                "release_date": None,
                "price_pln": 0.0,
                "positive_reviews": 0,
                "negative_reviews": 0,
                "positive_ratio": 0.0,
                "negative_ratio": 0.0
            }
            params_steam = {
                "appids": app_id,
                "cc": "PL",
                "l": "polish"
            }
            params_spy = {
                "request": "appdetails",
                "appid": app_id
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
            }
            try:
                response_steam = requests.get(url_steam, params=params_steam, headers=headers, timeout=10)
                if response_steam.status_code == 200:
                    steam_data = response_steam.json()
                    game_info = steam_data.get(str(app_id), {})
                    if game_info.get("success"):
                        data = game_info.get("data", {})
                        metadata['name'] = data.get("name")
                        platforms_dict = data.get("platforms", {})
                        metadata["platforms"] = [plat for plat, supp in platforms_dict.items() if supp]
                        metadata["release_date"] = data.get("release_date", {}).get("date")
                        if data.get("is_free"):
                            metadata["price_pln"] = 0.0
                        elif "price_overview" in data:
                            metadata["price_pln"] = data["price_overview"].get("final", 0) / 100.0
                response_spy = requests.get(url_steam_spy, params=params_spy, headers=headers, timeout=10)
                if response_spy.status_code == 200:
                    spy_data = response_spy.json()
                    pos = spy_data.get("positive", 0)
                    neg = spy_data.get("negative", 0)
                    metadata["positive_reviews"] = pos
                    metadata["negative_reviews"] = neg
                    total_reviews = pos + neg
                    if total_reviews > 0:
                        metadata["positive_ratio"] = round(pos / total_reviews, 4)
                        metadata["negative_ratio"] = round(neg / total_reviews, 4)
            except Exception as e:
                print(f"Error during getting data for app_id: {app_id}: {e}")
            self.games_information.append(metadata)
            time.sleep(1.5)

    def get_rest_data(self, num_users):
        for app_id in tqdm(self.games_id, desc="Pobieranie recenzji", unit="user and recommendation"):
            url = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
            collected_for_app = 0
            seen_ids = set()
            cursor = "*"
            while collected_for_app < num_users:
                batch_size = min(100, num_users - collected_for_app)
                params = {
                    "appid": app_id,
                    "json": "1",
                    "filter": "all",
                    "language": "all",
                    "num_per_page": batch_size,
                    "purchase_type": "all",
                    "cursor": cursor
                }
                if self.api_key:
                    params["key"] = self.api_key
                try:
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 429:
                        tqdm.write("HTTP 429 Too Many Requests - czekam 30s...")
                        time.sleep(30)
                        continue
                    if response.status_code != 200:
                        tqdm.write(f"HTTP ERROR: {response.status_code} dla APP ID: {app_id}")
                        break

                    if not response.text.strip():
                        tqdm.write(f"Pusta odpowiedź od Steama dla APP ID: {app_id}. Pomijam.")
                        break
                    try:
                        raw_data = response.json()
                    except Exception as e:
                        tqdm.write(f"Błąd parsowania JSON dla APP ID {app_id}: {e}")
                        break

                    data = raw_data.get("response", raw_data)
                    reviews = data.get("reviews", [])
                    if not reviews:
                        break
                    for review in reviews:
                        author = review.get("author", {})
                        steam_id = author.get("steamid")
                        if steam_id and steam_id not in seen_ids:
                            seen_ids.add(steam_id)
                            self.users_information.append({
                                "steam_id": steam_id,
                                "games_number": author.get("num_games_owned", 0),
                                "reviews_number": author.get("num_reviews", 0)
                            })
                            playtime_hours = round(author.get("playtime_forever", 0) / 60, 1)
                            self.recommendations.append({
                                "game_id": app_id,
                                "steam_id": steam_id,
                                "helpful": review.get("votes_up", 0),
                                "funny": review.get("votes_funny", 0),
                                "is_recommended": review.get("voted_up", False),
                                "hours": playtime_hours,
                                "review_id": review.get("recommendationid")
                            })
                            collected_for_app += 1
                            if collected_for_app >= num_users:
                                break
                    next_cursor = data.get("cursor")
                    if not next_cursor or next_cursor == cursor:
                        break
                    cursor = next_cursor
                    time.sleep(1.5)
                except Exception as e:
                    tqdm.write(f"Error during getting user data: {e}")
                    tqdm.write(f"APP ID: {app_id}")
                    break
            time.sleep(2)

    def save_data(self, save_path):
        if self.games_information:
            pd.DataFrame(self.games_information).to_csv(f"{save_path}/games_metadata.csv", index=False)
            print("SAVED games_metadata.csv")
        if self.users_information:
            pd.DataFrame(self.users_information).to_csv(f"{save_path}/users_information.csv", index=False)
            print("SAVED users_information.csv")
        if self.recommendations:
            pd.DataFrame(self.recommendations).to_csv(f"{save_path}/recommendations.csv", index=False)
            print("SAVED recommendations.csv")


if __name__ == "__main__":
    print("Data collector started")
    collector = DataCollector(5)
    print("DOWLOADING THE GAMES DATA")
    collector.get_games_data()
    print("DOWLOADING THE USERS AND RECOMMENDATIONS DATA")
    collector.get_rest_data(50)
    print("SAVING DATA")
    collector.save_data(save_path=r"C:\Users\patry\Desktop\projekt_systemy_obliczen_inteligentych\projekt2_system_rekomendacyjny\System-rekomendacyjny\dataset\steam_data")

