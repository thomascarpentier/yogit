"""
GraphQL queries used by yogit
"""
from tabulate import tabulate

from yogit.yogit.logger import echo_info
import yogit.api.statements as S
from yogit.api.client import GraphQLClient, RESTClient
from yogit.api.statement import prepare
from yogit.utils.dateutils import dt_for_str, days_ago_str


class Query:
    """ Represent a GitHub query """

    def __init__(self):
        self.response = None
        self.client = None

    def _handle_response(self):
        echo_info("Not fully implemented")

    def exec(self):
        """ Execute the query """
        raise NotImplementedError()

    def tabulate(self):
        """ Return tabulated result """
        raise NotImplementedError()

    def print(self):
        """ Print result """
        echo_info(self.response)


class GraphQLQuery(Query):
    def __init__(self, statement, variables=[]):
        super().__init__()
        self.statement = statement
        self.variables = variables

    def exec(self):
        prepared_statement = prepare(self.statement, self.variables)
        if self.client is None:
            self.client = GraphQLClient()
        self.response = self.client.get(prepared_statement)
        self._handle_response()


class RESTQuery(Query):
    def __init__(self, endpoint):
        super().__init__()
        self.endpoint = endpoint

    def exec(self):
        if self.client is None:
            self.client = RESTClient()
        self.response = self.client.get(self.endpoint)
        self._handle_response()


class LoginQuery(GraphQLQuery):
    def __init__(self):
        super().__init__(S.LOGIN_STATEMENT)
        self.client = GraphQLClient()
        self.login = None

    def _handle_response(self):
        self.login = self.response["data"]["viewer"]["login"]

    def get_login(self):
        return self.login


class ReviewRequestedQuery(GraphQLQuery):
    def __init__(self):
        super().__init__(S.REVIEW_REQUESTED_STATEMENT, [S.LOGIN_VARIABLE])
        self.data = []

    def _handle_response(self):
        for pr in self.response["data"]["search"]["edges"]:
            repo = pr["node"]["repository"]["nameWithOwner"]
            url = pr["node"]["url"]
            self.data.append([repo, url])
        self.data = sorted(self.data, key=lambda x: x[0])

    def print(self):
        echo_info(tabulate(self.data, headers=["REPO", "URL"]))


class RateLimitQuery(GraphQLQuery):
    def __init__(self):
        super().__init__(S.RATE_LIMIT_STATEMENT)
        self.limit = None
        self.remaining = None
        self.reset_at = None

    def _handle_response(self):
        rate_limit = self.response["data"]["rateLimit"]
        self.limit = rate_limit["limit"]
        self.remaining = rate_limit["remaining"]
        self.reset_at = rate_limit["resetAt"]

    def print(self):
        echo_info("{}/{} until {}".format(self.remaining, self.limit, self.reset_at))


class PullRequestListQuery(GraphQLQuery):
    def __init__(self):
        super().__init__(S.PULL_REQUEST_LIST_STATEMENT)
        self.data = []

    def _handle_response(self):
        for pr in self.response["data"]["viewer"]["pullRequests"]["edges"]:
            created = dt_for_str(pr["node"]["createdAt"])
            url = pr["node"]["url"]
            title = pr["node"]["title"]
            created_str = days_ago_str(created)
            self.data.append([created, created_str, url, title])
        # Sort by url, then by reversed string date:
        self.data = sorted(self.data, key=lambda x: x[2])
        self.data = sorted(self.data, key=lambda x: x[1], reverse=True)

    def print(self):
        echo_info(tabulate([x[1:] for x in self.data], headers=["CREATED", "URL", "TITLE"]))


class PullRequestContributionListQuery(GraphQLQuery):
    def __init__(self):
        super().__init__(S.PULL_REQUEST_CONTRIBUTION_LIST_STATEMENT, [S.TODAY_VARIABLE])
        self.data = []

    def _handle_response(self):
        pr_contributions = self.response["data"]["viewer"]["contributionsCollection"]["pullRequestContributions"][
            "edges"
        ]
        rv_contributions = self.response["data"]["viewer"]["contributionsCollection"]["pullRequestReviewContributions"][
            "edges"
        ]

        for pr_contribution in pr_contributions:
            url = pr_contribution["node"]["pullRequest"]["url"]
            state = pr_contribution["node"]["pullRequest"]["state"]
            self.data.append([url, "OWNER", state])

        for rv_contribution in rv_contributions:
            url = rv_contribution["node"]["pullRequest"]["url"]
            state = rv_contribution["node"]["pullRequestReview"]["state"]
            self.data.append([url, "REVIEWER", state])

        self.data = sorted(self.data, key=lambda x: (x[0], x[1], x[2]))

    def tabulate(self):
        return tabulate(self.data, headers=["PULL REQUEST", "ROLE", "STATE"])

    def print(self):
        echo_info(self.tabulate())


class BranchListQuery(GraphQLQuery):
    def __init__(self, emails=None):
        super().__init__(S.BRANCH_LIST_STATEMENT)
        self.data = []
        self.emails = emails

    def _handle_response(self):
        for repo in self.response["data"]["viewer"]["repositoriesContributedTo"]["edges"]:
            repo_url = repo["node"]["url"]
            for branch in repo["node"]["refs"]["edges"]:
                branch_name = branch["node"]["name"]
                author_email = branch["node"]["target"]["author"]["email"]
                pr_list = []
                for pr in branch["node"]["associatedPullRequests"]["edges"]:
                    pr_list.append(pr["node"]["url"])
                pr_list = sorted(pr_list)
                if self.emails is not None:
                    if author_email in self.emails:
                        self.data.append([repo_url, branch_name, "\n".join(pr_list)])

            self.data = sorted(self.data, key=lambda x: (x[0], x[1]))

    def print(self):
        echo_info(tabulate(self.data, headers=["REPO", "BRANCH", "PULL REQUEST"]))


class EmailQuery(RESTQuery):
    def __init__(self):
        super().__init__("/user/emails")
        self.emails = None

    def _handle_response(self):
        self.emails = [x["email"] for x in self.response]

    def get_emails(self):
        return self.emails
