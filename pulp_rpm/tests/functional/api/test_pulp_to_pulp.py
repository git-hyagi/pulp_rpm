"""Tests that verify download of content served by Pulp."""
from pulp_smash.pulp3.bindings import PulpTestCase, monitor_task
from pulp_smash.pulp3.utils import (
    gen_distribution,
    gen_repo,
    get_added_content_summary,
    get_content_summary,
)

from pulp_rpm.tests.functional.constants import RPM_KICKSTART_FIXTURE_URL
from pulp_rpm.tests.functional.utils import (
    gen_rpm_client,
    gen_rpm_remote,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import (
    DistributionsRpmApi,
    PublicationsRpmApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
    RpmRpmPublication,
)


class SynctoSyncTestCase(PulpTestCase):
    """Sync repositories with the rpm plugin."""

    def test_immediate(self):
        """Sync content from Pulp with an immediate policy."""
        self.do_test("immediate")

    def test_on_demand(self):
        """Sync content from Pulp with an on_demand policy."""
        self.do_test("on_demand")

    def test_streamed(self):
        """Sync content from Pulp with an streamed policy."""
        self.do_test("streamed")

    def do_test(self, policy):
        """Verify whether content served by Pulp can be synced.

        The initial sync to Pulp is one of many different download policies, the second sync is
        immediate in order to exercise downloading all of the files.

        Do the following:

        1. Create, populate, publish, and distribute a repository.
        2. Sync other repository using as remote url,
        the distribution base_url from the previous repository.

        """
        client = gen_rpm_client()
        repo_api = RepositoriesRpmApi(client)
        remote_api = RemotesRpmApi(client)
        publications = PublicationsRpmApi(client)
        distributions = DistributionsRpmApi(client)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=RPM_KICKSTART_FIXTURE_URL, policy=policy)
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        # Sync a Repository
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = repo_api.read(repo.pulp_href)

        # Create a publication.
        publish_data = RpmRpmPublication(
            repository=repo.pulp_href,
            metadata_checksum_type="sha384",
            package_checksum_type="sha224",
        )
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        self.addCleanup(publications.delete, publication_href)

        # Create a distribution.
        body = gen_distribution()
        body["publication"] = publication_href
        distribution_response = distributions.create(body)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = distributions.read(created_resources[0])
        self.addCleanup(distributions.delete, distribution.pulp_href)

        # Create another repo pointing to distribution base_url
        repo2 = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo2.pulp_href)

        body = gen_rpm_remote(url=distribution.base_url, policy="immediate")
        remote2 = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote2.pulp_href)

        # Sync a Repository
        repository_sync_data = RpmRepositorySyncURL(remote=remote2.pulp_href)
        sync_response = repo_api.sync(repo2.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo2 = repo_api.read(repo2.pulp_href)

        summary = get_content_summary(repo.to_dict())
        summary2 = get_content_summary(repo2.to_dict())
        self.assertDictEqual(summary, summary2)

        added = get_added_content_summary(repo.to_dict())
        added2 = get_added_content_summary(repo2.to_dict())
        self.assertDictEqual(added, added2)
