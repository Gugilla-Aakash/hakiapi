"""
Example usage of GitHubClient.

Before running:

    export GITHUB_TOKEN="your_personal_access_token"
"""

import os
from pprint import pprint

from hakiapi.clients.github import GitHubClient


def main() -> None:
    github = GitHubClient(token=os.environ["GITHUB_TOKEN"])

    username = "Gugilla-Aakash"

    print("== User ==")
    pprint(github.get_user(username))

    print("\n== Search Users ==")
    pprint(github.search_users("torvalds")["items"][:3])

    print("\n== All Search Users ==")
    for user in github.get_all_search_users("python"):
        print(user["login"])
        break

    print("\n== User Repositories ==")
    repos = github.get_user_repos(username)
    print(f"Found {len(repos)} repositories.")

    print("\n== All User Repositories ==")
    print(f"Total: {len(list(github.get_all_user_repos(username)))}")

    if repos:
        repo = repos[0]["name"]

        print("\n== Repository Languages ==")
        pprint(github.get_repo_languages(username, repo))

    print("\n== Aggregate Languages ==")
    pprint(github.get_aggregate_user_languages(username))

    print("\n== User Activity ==")
    pprint(github.get_user_authored_activity(username))

    print("\n== Execute GraphQL ==")
    result = github.execute_graphql(
        """
        query($login: String!) {
          user(login: $login) {
            login
            name
          }
        }
        """,
        variables={"login": username},
    )
    pprint(result)

    print("\n== User Contributions ==")
    pprint(github.get_user_contributions(username))


if __name__ == "__main__":
    main()
