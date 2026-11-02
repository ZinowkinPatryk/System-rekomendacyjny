import time
import pandas as pd
import requests

class DataCollector:
    def __init__(self, data_limit: int = 3000):
        self.limit = data_limit
        self._url_steam_spy = "https://steamspy.com/api.php"
        self._url_steam_games = "https://store.steampowered.com/api/appdetails"
        self._id_list = []
        self.__data_dict = {}

    def get_games_id(self):
        print("Getting games ids")
        pages_needed = (self.limit // 1000) + 1
        head = {'User-Agent': 'Mozilla/5.0'}
        print(self.limit)
        try:
            for page in range(pages_needed):
                params = {"request": "all", "page": str(page)}
                response = requests.get(self._url_steam_spy, params=params, headers=head)
                response.raise_for_status()
                data = response.json()
                self._id_list.extend(list(data.keys()))
                time.sleep(3)
                if len(self._id_list) >= self.limit:
                    break
            print("Succes")
            print(self._id_list)
            print(len(self._id_list))
            return self._id_list
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            raise e

    def get_games_data(self, save_internals: int = 100) -> None:
        self.get_games_id()
        print("Getting games data")
        head = {'User-Agent': 'Mozilla/5.0'}
        try:
            for id in self._id_list:
                params = {"appids": id}
                response = requests.get(self._url_steam_games, params=params, headers=head)
                response.raise_for_status()
                if response.status_code == 429:
                    time.sleep(15)
                    continue
                response.raise_for_status()
                data = response.json()
                if data and str(id) in data and data[str(id)].get('success'):
                    game_info = data[str(id)]['data']
                    self.__data_dict[id] = {
                        "name" : game_info.get('name', 'unknown'),
                        "short_description" : game_info.get('short_description' , 'unknown'),
                        "genres": ", ".join([g["description"] for g in game_info.get("genres", [])]) if "genres" in game_info else "",
                        "metacritic_score": game_info.get("metacritic", {}).get("score", None)
                    }
                if (len(self._id_list) % save_internals) == 0:
                    self.save_data(self.__data_dict)
                time.sleep(3)
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            raise e

    @staticmethod
    def save_data(__data_dict: dict) -> None:
        if not __data_dict:
            raise Exception("Error SOMETHING REALLY GOES WRONG HERE")
        df = pd.DataFrame.from_dict(__data_dict, orient='index')
        df = df.rename_axis('app_id').reset_index()
        df.to_csv("dataset_steam.csv", index=False, encoding='utf-8')
        print("Success saved")

    def clear_data(self):
        pass

    @property
    def data_results(self):
        return self.__data_dict


if __name__ == "__main__":
    collector = DataCollector(10)
    collector.get_games_data()
    for key in collector.data_results.keys():
        print(f"{key}: {collector.data_results[key]}")
