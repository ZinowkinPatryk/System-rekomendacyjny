from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors
import pandas as pd


class RecommendationSystem:
    def __init__(self, path):
        self.df = pd.read_csv(path)
        self.df, self.vectorizer, self.tfidf_matrix = self.vectorizer(self.df)

    @staticmethod
    def vectorizer(df):
        if "metacritic_score" in df.columns:
            df = df.dropna(subset=["metacritic_score"])
        df['short_description'] = df['short_description'].fillna("")
        df['genres'] = df['genres'].fillna("")
        df = df.reset_index(drop=True)
        df['combined_features'] = df['short_description'] +" "+df['genres']
        vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
        tfidf_matrix = vectorizer.fit_transform(df['combined_features'])
        return df, vectorizer, tfidf_matrix

    @staticmethod
    def recommendation_based_on_similarity_objects(tfidf_matrix, game_index: int, top_k: int = 5):
        game_vector = tfidf_matrix[game_index]
        sim_scores = cosine_similarity(game_vector, tfidf_matrix).flatten()
        sorted_indices = sim_scores.argsort()[::-1]
        top_indices = []
        scores = []
        for idx in sorted_indices:
            if idx != game_index:
                top_indices.append(idx)
                scores.append(sim_scores[idx])
            if len(top_indices) == top_k:
                break
        return top_indices, scores

    @staticmethod
    def k_nearest_neighbor(tfidf_matrix, game_index: int, top_k: int = 5):
        knn = NearestNeighbors(n_neighbors=top_k+1, metric='cosine').fit(tfidf_matrix)
        game_vector = tfidf_matrix[game_index]
        distances, indices = knn.kneighbors(game_vector)
        distances = distances.flatten()
        indices = indices.flatten()
        similarities = 1 - distances
        top_indices = []
        scores = []
        for i, idx in enumerate(indices):
            if idx != game_index:
                top_indices.append(idx)
                scores.append(similarities[i])
            if len(top_indices) == top_k:
                break
        return top_indices, scores

    def recommendation_list(self, search_query: str, algorithm: str = 'knn', top_k: int = 5):
        match = self.df[self.df['name'].str.contains(search_query, case=False, na=False)]
        if match.empty:
            return {"status": "error", "message": "NOT FOUND"}
        game_index = match.index[0]
        exact_name = self.df.loc[game_index, 'name']
        if algorithm == 'cosine':
            indices, scores = self.recommendation_based_on_similarity_objects(
                self.tfidf_matrix, game_index, top_k=top_k
            )
        elif algorithm == 'knn':
            indices, scores = self.recommendation_based_on_similarity_objects(
                self.tfidf_matrix, game_index, top_k=top_k
            )
        else:
            return {"status": "error", "message": "WRONG ALGORITHM"}
        recommendation_list = []
        col_genre = 'genre' if 'genre' in self.df.columns else 'genres'

        for idx, score  in zip(indices, scores):
            recommendation_list.append(
                {
                    "name": exact_name,
                    "genre": col_genre,
                    "similarity": round(float(score), 4),
                }
            )
        return {
            "status": "success",
            "target_game": exact_name,
            "results": recommendation_list
        }

if __name__ == "__main__":
    system = RecommendationSystem("dataset_steam.csv")
    ui_response = system.recommendation_list(search_query="Cyberpunk 2077", algorithm="cosine", top_k=3)
    if ui_response["status"] == "success":
        print(f"Rekomendacje dla: {ui_response['target_game']}")
        for rec in ui_response["results"]:
            print(f"- {rec['name']} (Podobieństwo: {rec['similarity']})")
    else:
        print(ui_response["message"])