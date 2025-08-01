from __future__ import annotations

from collections.abc import Sequence
from typing import Unpack, final

from loguru import logger
from notte_core.common.resource import SyncResource
from notte_core.common.telemetry import track_usage
from notte_core.credentials.base import (
    BaseVault,
    Credential,
    CredentialsDict,
    CreditCardDict,
    Vault,
)
from pydantic import BaseModel
from typing_extensions import override

from notte_sdk.endpoints.base import BaseClient, NotteEndpoint
from notte_sdk.types import (
    AddCredentialsRequest,
    AddCredentialsRequestDict,
    AddCredentialsResponse,
    AddCreditCardRequest,
    AddCreditCardRequestDict,
    AddCreditCardResponse,
    DeleteCredentialsRequest,
    DeleteCredentialsRequestDict,
    DeleteCredentialsResponse,
    DeleteCreditCardRequest,
    DeleteCreditCardRequestDict,
    DeleteCreditCardResponse,
    DeleteVaultRequest,
    DeleteVaultRequestDict,
    DeleteVaultResponse,
    GetCredentialsRequest,
    GetCredentialsRequestDict,
    GetCredentialsResponse,
    GetCreditCardRequest,
    GetCreditCardRequestDict,
    GetCreditCardResponse,
    ListCredentialsRequest,
    ListCredentialsRequestDict,
    ListCredentialsResponse,
    VaultCreateRequest,
    VaultCreateRequestDict,
    VaultListRequest,
    VaultListRequestDict,
)


# DEFINED HERE TO SIMPLIFY CIRCULAR DEPENDENCY
# SHOULD ONLY BE INVOKED FROM ENDPOINT ANYWAY
@final
class NotteVault(BaseVault, SyncResource):
    """Vault that fetches credentials stored using the sdk"""

    def __init__(self, vault_id: str, vault_client: VaultsClient):
        super().__init__()
        if len(vault_id) == 0:
            raise ValueError("Vault ID cannot be empty")

        self.vault_id: str = vault_id
        self.vault_client = vault_client

    @override
    def start(self) -> None:
        pass

    @override
    def stop(self) -> None:
        logger.info(f"[Vault] {self.vault_id} deleted. All credentials have been deleted.")
        self.delete()

    @override
    async def _add_credentials(self, url: str, creds: CredentialsDict) -> None:
        _ = self.vault_client.add_or_update_credentials(self.vault_id, url=url, **creds)

    @override
    async def _get_credentials_impl(self, url: str) -> CredentialsDict | None:
        return self.vault_client.get_credentials(vault_id=self.vault_id, url=url).credentials

    @override
    async def delete_credentials_async(self, url: str) -> None:
        _ = self.vault_client.delete_credentials(vault_id=self.vault_id, url=url)

    @override
    async def set_credit_card_async(self, **kwargs: Unpack[CreditCardDict]) -> None:
        _ = self.vault_client.set_credit_card(self.vault_id, **kwargs)

    @override
    async def get_credit_card_async(self) -> CreditCardDict:
        return self.vault_client.get_credit_card(self.vault_id).credit_card

    @override
    async def list_credentials_async(self) -> list[Credential]:
        return self.vault_client.list_credentials(self.vault_id).credentials

    @override
    async def delete_credit_card_async(self) -> None:
        _ = self.vault_client.delete_credit_card(self.vault_id)

    def delete(self) -> None:
        _ = self.vault_client.delete(self.vault_id)


@final
class VaultsClient(BaseClient):
    """
    Client for the Notte API.

    Note: this client is only able to handle one session at a time.
    If you need to handle multiple sessions, you need to create a new client for each session.
    """

    # Session
    CREATE_VAULT = "create"
    ADD_CREDENTIALS = "{vault_id}/credentials"
    GET_CREDENTIALS = "{vault_id}/credentials"
    DELETE_CREDENTIALS = "{vault_id}/credentials"
    ADD_CREDIT_CARD = "{vault_id}/card"
    GET_CREDIT_CARD = "{vault_id}/card"
    DELETE_CREDIT_CARD = "{vault_id}/card"
    LIST_VAULTS = ""
    LIST_CREDENTIALS = "{vault_id}"
    DELETE_VAULT = "{vault_id}"

    @staticmethod
    def _delete_vault_endpoint(vault_id: str) -> NotteEndpoint[DeleteVaultResponse]:
        """
        Returns a NotteEndpoint configured for deleting a vault.

        Args:
            vault_id: The ID of the vault to delete.

        Returns:
            A NotteEndpoint with the DELETE method that expects a DeleteVaultResponse.
        """
        return NotteEndpoint(
            path=VaultsClient.DELETE_VAULT.format(vault_id=vault_id),
            response=DeleteVaultResponse,
            method="DELETE",
        )

    @staticmethod
    def _list_credentials_endpoint(vault_id: str) -> NotteEndpoint[ListCredentialsResponse]:
        """
        Returns a NotteEndpoint configured for listing credentials in a vault.

        Args:
            vault_id: The ID of the vault to list credentials from.

        Returns:
            A NotteEndpoint with the GET method that expects a ListCredentialsResponse.
        """
        return NotteEndpoint(
            path=VaultsClient.LIST_CREDENTIALS.format(vault_id=vault_id),
            response=ListCredentialsResponse,
            method="GET",
        )

    @staticmethod
    def _list_endpoint() -> NotteEndpoint[Vault]:
        """
        Returns a NotteEndpoint configured for listing all vaults.

        Returns:
            A NotteEndpoint with the GET method that expects a ListVaultsResponse.
        """
        return NotteEndpoint(
            path=VaultsClient.LIST_VAULTS,
            response=Vault,
            method="GET",
        )

    @staticmethod
    def _delete_credit_card_endpoint(vault_id: str) -> NotteEndpoint[DeleteCreditCardResponse]:
        """
        Returns a NotteEndpoint configured for deleting a credit card from a vault.

        Args:
            vault_id: The ID of the vault containing the credit card to delete.

        Returns:
            A NotteEndpoint with the DELETE method that expects a DeleteCreditCardResponse.
        """
        return NotteEndpoint(
            path=VaultsClient.DELETE_CREDIT_CARD.format(vault_id=vault_id),
            response=DeleteCreditCardResponse,
            method="DELETE",
        )

    @staticmethod
    def _get_credit_card_endpoint(vault_id: str) -> NotteEndpoint[GetCreditCardResponse]:
        """
        Returns a NotteEndpoint configured for retrieving a credit card from a vault.

        Args:
            vault_id: The ID of the vault containing the credit card to retrieve.

        Returns:
            A NotteEndpoint with the GET method that expects a GetCreditCardResponse.
        """
        return NotteEndpoint(
            path=VaultsClient.GET_CREDIT_CARD.format(vault_id=vault_id),
            response=GetCreditCardResponse,
            method="GET",
        )

    @staticmethod
    def _set_credit_card_endpoint(vault_id: str) -> NotteEndpoint[AddCreditCardResponse]:
        """
        Returns a NotteEndpoint configured for setting a credit card in a vault.

        Args:
            vault_id: The ID of the vault to add the credit card to.

        Returns:
            A NotteEndpoint with the POST method that expects an AddCreditCardResponse.
        """
        return NotteEndpoint(
            path=VaultsClient.ADD_CREDIT_CARD.format(vault_id=vault_id),
            response=AddCreditCardResponse,
            method="POST",
        )

    @staticmethod
    def _delete_credentials_endpoint(vault_id: str) -> NotteEndpoint[DeleteCredentialsResponse]:
        """
        Returns a NotteEndpoint configured for deleting credentials from a vault.

        Args:
            vault_id: The ID of the vault containing the credentials to delete.

        Returns:
            A NotteEndpoint with the DELETE method that expects a DeleteCredentialsResponse.
        """
        return NotteEndpoint(
            path=VaultsClient.DELETE_CREDENTIALS.format(vault_id=vault_id),
            response=DeleteCredentialsResponse,
            method="DELETE",
        )

    @staticmethod
    def _get_credential_endpoint(vault_id: str) -> NotteEndpoint[GetCredentialsResponse]:
        """
        Returns a NotteEndpoint configured for retrieving credentials from a vault.

        Args:
            vault_id: The ID of the vault containing the credentials to retrieve.

        Returns:
            A NotteEndpoint with the GET method that expects a GetCredentialsResponse.
        """
        return NotteEndpoint(
            path=VaultsClient.GET_CREDENTIALS.format(vault_id=vault_id),
            response=GetCredentialsResponse,
            method="GET",
        )

    @staticmethod
    def _add_or_update_credentials_endpoint(vault_id: str) -> NotteEndpoint[AddCredentialsResponse]:
        """
        Returns a NotteEndpoint configured for adding or updating credentials in a vault.

        Args:
            vault_id: The ID of the vault to add or update credentials in.

        Returns:
            A NotteEndpoint with the POST method that expects an AddCredentialsResponse.
        """
        return NotteEndpoint(
            path=VaultsClient.ADD_CREDENTIALS.format(vault_id=vault_id),
            response=AddCredentialsResponse,
            method="POST",
        )

    def __init__(
        self,
        api_key: str | None = None,
        server_url: str | None = None,
        verbose: bool = False,
    ):
        """
        Initialize a VaultsClient instance.

        Initializes the client with an optional API key for vault management.
        """
        super().__init__(base_endpoint_path="vaults", server_url=server_url, api_key=api_key, verbose=verbose)

    @staticmethod
    def _create_vault_endpoint() -> NotteEndpoint[Vault]:
        """
        Returns a NotteEndpoint configured for creating a new vault.

        Returns:
            A NotteEndpoint with the POST method that expects a Vault response.
        """
        return NotteEndpoint(
            path=VaultsClient.CREATE_VAULT,
            response=Vault,
            method="POST",
        )

    @override
    @staticmethod
    def endpoints() -> Sequence[NotteEndpoint[BaseModel]]:
        """Returns the available vault endpoints.

        Aggregates endpoints from VaultsClient for creating vaults, reading creds, etc..."""
        return [
            VaultsClient._create_vault_endpoint(),
            VaultsClient._add_or_update_credentials_endpoint(""),
            VaultsClient._get_credential_endpoint(""),
            VaultsClient._delete_credentials_endpoint(""),
            VaultsClient._set_credit_card_endpoint(""),
            VaultsClient._get_credit_card_endpoint(""),
            VaultsClient._delete_credit_card_endpoint(""),
            VaultsClient._list_endpoint(),
            VaultsClient._list_credentials_endpoint(""),
            VaultsClient._delete_vault_endpoint(""),
        ]

    @track_usage("cloud.vault.get")
    def get(self, vault_id: str) -> NotteVault:
        """
        Get vault by id

        Args:
            vault_id: str: the vault id

        Returns:
            NotteVault: The vault with provided id
        """
        # try to list credentials to force exception if vault does not exist
        _ = self.list_credentials(vault_id)
        return NotteVault(vault_id, vault_client=self)

    @track_usage("cloud.vault.create")
    def create(self, **data: Unpack[VaultCreateRequestDict]) -> NotteVault:
        """
        Create vault

        Args:
            **data: Unpacked dictionary containing the vault creation parameters.

        Returns:
            NotteVault: The created vault
        """
        params = VaultCreateRequest.model_validate(data)
        response = self.request(VaultsClient._create_vault_endpoint().with_request(params))
        return NotteVault(response.vault_id, vault_client=self)

    @track_usage("cloud.vault.credentials.add")
    def add_or_update_credentials(
        self, vault_id: str, **data: Unpack[AddCredentialsRequestDict]
    ) -> AddCredentialsResponse:
        """
        Adds or updates credentials in a vault.

        Args:
            vault_id: ID of the vault to add or update credentials in.
            **data: Unpacked dictionary containing credential information.

        Returns:
            AddCredentialsResponse: Response from the add credentials endpoint.
        """
        params = AddCredentialsRequest.from_dict(data)
        response = self.request(self._add_or_update_credentials_endpoint(vault_id).with_request(params))
        return response

    @track_usage("cloud.vault.credentials.get")
    def get_credentials(self, vault_id: str, **data: Unpack[GetCredentialsRequestDict]) -> GetCredentialsResponse:
        """
        Retrieves credentials from a vault.

        Args:
            vault_id: ID of the vault containing the credentials.
            **data: Unpacked dictionary containing parameters for the request.

        Returns:
            GetCredentialsResponse: Response containing the requested credentials.
        """
        params = GetCredentialsRequest.model_validate(data)
        response = self.request(self._get_credential_endpoint(vault_id).with_params(params))
        return response

    @track_usage("cloud.vault.credentials.delete")
    def delete_credentials(
        self, vault_id: str, **data: Unpack[DeleteCredentialsRequestDict]
    ) -> DeleteCredentialsResponse:
        """
        Deletes credentials from a vault.

        Args:
            vault_id: ID of the vault containing the credentials to delete.
            **data: Unpacked dictionary containing parameters specifying the credentials to delete.

        Returns:
            DeleteCredentialsResponse: Response from the delete credentials endpoint.
        """
        params = DeleteCredentialsRequest.model_validate(data)
        response = self.request(self._delete_credentials_endpoint(vault_id).with_params(params))
        return response

    @track_usage("cloud.vault.delete")
    def delete(self, vault_id: str, **data: Unpack[DeleteVaultRequestDict]) -> DeleteVaultResponse:
        """
        Deletes a vault.

        Args:
            vault_id: ID of the vault to delete.
            **data: Unpacked dictionary containing parameters for the request.

        Returns:
            DeleteVaultResponse: Response from the delete vault endpoint.
        """
        params = DeleteVaultRequest.model_validate(data)
        response = self.request(self._delete_vault_endpoint(vault_id).with_params(params))
        return response

    @track_usage("cloud.vault.credentials.list")
    def list_credentials(self, vault_id: str, **data: Unpack[ListCredentialsRequestDict]) -> ListCredentialsResponse:
        """
        Lists credentials in a vault.

        Args:
            vault_id: ID of the vault to list credentials from.
            **data: Unpacked dictionary containing parameters for the request.

        Returns:
            ListCredentialsResponse: Response containing the list of credentials.
        """
        params = ListCredentialsRequest.model_validate(data)
        response = self.request(self._list_credentials_endpoint(vault_id).with_params(params))
        return response

    @track_usage("cloud.vault.list")
    def list(self, **data: Unpack[VaultListRequestDict]) -> Sequence[Vault]:
        """
        Lists all available vaults.

        Args:
            **data: Unpacked dictionary containing parameters for the request.

        Returns:
            ListVaultsResponse: Response containing the list of vaults.
        """
        params = VaultListRequest.model_validate(data)
        endpoint = self._list_endpoint().with_params(params)
        return self.request_list(endpoint)

    @track_usage("cloud.vault.credit_card.delete")
    def delete_credit_card(
        self, vault_id: str, **data: Unpack[DeleteCreditCardRequestDict]
    ) -> DeleteCreditCardResponse:
        """
        Deletes a credit card from a vault.

        Args:
            vault_id: ID of the vault containing the credit card to delete.
            **data: Unpacked dictionary containing parameters specifying the credit card to delete.

        Returns:
            DeleteCreditCardResponse: Response from the delete credit card endpoint.
        """
        params = DeleteCreditCardRequest.model_validate(data)
        response = self.request(self._delete_credit_card_endpoint(vault_id).with_params(params))
        return response

    @track_usage("cloud.vault.credit_card.get")
    def get_credit_card(self, vault_id: str, **data: Unpack[GetCreditCardRequestDict]) -> GetCreditCardResponse:
        """
        Retrieves a credit card from a vault.

        Args:
            vault_id: ID of the vault containing the credit card.
            **data: Unpacked dictionary containing parameters for the request.

        Returns:
            GetCreditCardResponse: Response containing the requested credit card information.
        """
        params = GetCreditCardRequest.model_validate(data)
        response = self.request(self._get_credit_card_endpoint(vault_id).with_params(params))
        return response

    @track_usage("cloud.vault.credit_card.set")
    def set_credit_card(self, vault_id: str, **data: Unpack[AddCreditCardRequestDict]) -> AddCreditCardResponse:
        """
        Sets a credit card in a vault.

        Args:
            vault_id: ID of the vault to add the credit card to.
            **data: Unpacked dictionary containing credit card information.

        Returns:
            AddCreditCardResponse: Response from the add credit card endpoint.
        """
        params = AddCreditCardRequest.from_dict(data)
        response = self.request(self._set_credit_card_endpoint(vault_id).with_request(params))
        return response


@final
class RemoteVaultFactory:
    def __init__(self, client: VaultsClient):
        self.client = client

    def __call__(self, vault_id: str | None = None, **data: Unpack[VaultCreateRequestDict]) -> NotteVault:
        if vault_id is None:
            vault = self.client.create(**data)
            logger.warning(
                f"[Vault] {vault.vault_id} created since no vault id was provided. Please store this to retrieve it later."
            )
            return vault
        return self.client.get(vault_id)
