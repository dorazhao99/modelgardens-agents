import asyncio
from gum import gum

class GumTools():

    def __init__(self, name: str, model: str = "gpt-4.1"):
        self.gum_instance = gum(name, model=model)
        self.name = name
        self.model = model
        asyncio.run(self.gum_instance.connect_db())

    def search_user_data(self, search_query: str):
        """
        Search the User model database for answers about the user's data.

        Args:
            query: The query to search the User model database for.  This should be a BM25 style optimal query for information seeking about the user's data.

        Returns:
            A string of the best information we have about the user that pertains to this question.  These observations are NOT guaranteed to be correct.
        """
        # Query the GUM database for the user data
        propositions = asyncio.run(self.gum_instance.query(search_query, limit=10))

        # Sort by relevance score
        propositions = sorted(propositions, key=lambda x: x[1], reverse=True)

        output = [f"=== User ({self.name}) Data === \n==="] + [f"[{i}] {proposition.text} \n(reasoning: {proposition.reasoning}) \n(confidence: {proposition.confidence}) \n(created_at: {proposition.created_at.isoformat()}) \n(relevance_score: {relevance_score}) \n===" for i, (proposition, relevance_score) in enumerate(propositions)]
        return "\n".join(output)

if __name__ == "__main__":
    gum_tools = GumTools(name="Michael Ryan", model="gpt-4.1")
    print(gum_tools.search_user_data("What is michael working on?"))