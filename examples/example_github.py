"""
Example usage of the HakiAPI GitHub Client.
"""

from hakiapi.clients.github import GitHubClient


def main() -> None:
    with GitHubClient() as gh:
        target_user = "Gugilla-Aakash"

        user_data = gh.get_user(target_user)

        print(f"User: {user_data.get('name')}")
        print(f"Public Repos: {user_data.get('public_repos')}")

        print(f"Aggregating all languages for {target_user} across public repos...")

        lang_stats = gh.get_aggregate_user_languages(
            target_user, params={"per_page": 5}
        )

        total_bytes = sum(lang_stats.values())
        print("\nLanguage Breakdown (by byte allocation):")
        for lang, byte_count in sorted(
            lang_stats.items(), key=lambda item: item[1], reverse=True
        ):
            percentage = (byte_count / total_bytes) * 100 if total_bytes > 0 else 0
            print(f"- {lang}: {byte_count} bytes ({percentage:.2f}%)")


if __name__ == "__main__":
    main()
