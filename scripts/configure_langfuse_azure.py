"""Provision Langfuse Key Vault references using local .env credentials.

Run with the Azure CLI account that manages this deployment. Credentials are
sent directly to Key Vault over HTTPS, never printed or passed in CLI arguments.
"""
import json
import shutil
import subprocess
from pathlib import Path

import httpx
from dotenv import dotenv_values


def main():
    values = dotenv_values(Path(__file__).resolve().parents[1] / '.env')
    for key in ('LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY'):
        if not values.get(key):
            raise SystemExit(f'Missing {key} in local .env')
    az = shutil.which('az') or shutil.which('az.cmd')
    if not az:
        raise SystemExit('Azure CLI is required')

    def cli(*args):
        result = subprocess.run([az, *args, '-o', 'json'], capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(f'Azure operation failed: {args[0]} {args[1]} (exit {result.returncode})')
        return json.loads(result.stdout or 'null')

    base_url = values.get('LANGFUSE_BASE_URL') or 'https://cloud.langfuse.com'
    auth = (values['LANGFUSE_PUBLIC_KEY'], values['LANGFUSE_SECRET_KEY'])
    with httpx.Client(timeout=30) as client:
        check = client.get(base_url.rstrip('/') + '/api/public/projects', auth=auth)
        if check.status_code != 200:
            raise SystemExit(f'Langfuse credential check failed: HTTP {check.status_code}')
        token = cli('account', 'get-access-token', '--resource', 'https://vault.azure.net')['accessToken']
        vault = 'https://mtg-assistant-kv-40p02b.vault.azure.net'
        for name, key in [('langfuse-public-key', 'LANGFUSE_PUBLIC_KEY'), ('langfuse-secret-key', 'LANGFUSE_SECRET_KEY')]:
            response = client.put(f'{vault}/secrets/{name}?api-version=7.4',
                                  headers={'Authorization': f'Bearer {token}'}, json={'value': values[key]})
            if response.status_code != 200:
                raise SystemExit(f'Key Vault write failed: HTTP {response.status_code}')
    identity = cli('identity', 'show', '-n', 'mtg-assistant-ca-identity-40p02b', '-g', 'mtg-assistant-prod-rg')['id']
    cli('containerapp', 'secret', 'set', '-n', 'mtg-assistant-app', '-g', 'mtg-assistant-prod-rg', '--secrets',
        f'langfuse-public-key=keyvaultref:{vault}/secrets/langfuse-public-key,identityref:{identity}',
        f'langfuse-secret-key=keyvaultref:{vault}/secrets/langfuse-secret-key,identityref:{identity}')
    cli('containerapp', 'update', '-n', 'mtg-assistant-app', '-g', 'mtg-assistant-prod-rg', '--set-env-vars',
        'LANGFUSE_ENABLED=true', 'LANGFUSE_PUBLIC_KEY=secretref:langfuse-public-key',
        'LANGFUSE_SECRET_KEY=secretref:langfuse-secret-key', f'LANGFUSE_BASE_URL={base_url}',
        f'LANGFUSE_CAPTURE_CONTENT={values.get("LANGFUSE_CAPTURE_CONTENT", "true")}')
    print('Langfuse authenticated; secrets stored in Key Vault; production environment updated.')


if __name__ == '__main__':
    main()
