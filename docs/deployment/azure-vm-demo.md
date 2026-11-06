# Azure single-VM demo deployment

This guide documents the Azure Portal and server steps used to publish the AssureAI
frontend, API, worker, PostgreSQL, and Redis on one Ubuntu virtual machine.

The deployed showcase is available at:

- Application: <http://52.172.254.68/>
- API readiness: <http://52.172.254.68/ready>

This is a demonstration deployment. It intentionally uses a public IP over HTTP and the
current application has no authentication. Do not upload confidential, personal, or
customer documents. Add authentication and TLS before using this pattern for real data.

## Resulting architecture

    Internet
       |
       | HTTP 80
       v
    Azure NSG + Ubuntu UFW
       |
       v
    Nginx / React
       |
       +-- /api/* --> FastAPI --> PostgreSQL
       |                 |
       |                 +-----> Redis --> Dramatiq worker
       |
       +-- static React application

Only SSH port 22 and web port 80 listen on the VM. FastAPI port 8000, PostgreSQL port
5432, Redis port 6379, and the Vite development port 5173 are not published.

## 1. Open the VM creation workflow

In the Azure Portal:

1. Search for **Virtual machines**.
2. Open **Virtual machines**.
3. Select **Create** and then **Azure virtual machine**.

## 2. Configure Basics

The deployment used these values:

| Setting | Value |
| --- | --- |
| Subscription | Azure subscription 1 |
| Resource group | rg-assureai-prod |
| VM name | vm-assureai-prod-01 |
| Region | Central India |
| Availability | No infrastructure redundancy required |
| Security type | Trusted launch virtual machines |
| Secure boot | Enabled |
| vTPM | Enabled |
| Image | Ubuntu Server 24.04 LTS, x64 Gen2 |
| Architecture | x64 |
| Size | Standard B2ls v2, 2 vCPU, 4 GiB RAM |
| Authentication | SSH public key |
| Username | azureuser |
| SSH key source | Generate new key pair |
| SSH key type | Ed25519 |
| Key pair name | assureai-prod-key |
| Azure Spot | Disabled |

The portal showed USD 0.0448/hour for compute when this VM was created on
November 6, 2026. Azure prices and available sizes change; always use the price shown
for the selected subscription, region, and date.

Download the generated private key when prompted. Keep it outside the repository and
never share or commit it.

## 3. Configure Disks

Use:

| Setting | Value |
| --- | --- |
| OS disk size | 64 GiB |
| OS disk type | Standard SSD LRS |
| Delete OS disk with VM | No |
| Key management | Platform-managed key |
| Ultra Disk | Disabled |
| Data disks | None |
| Ephemeral OS disk | None |

Keeping the OS disk when deleting the VM helps protect against an accidental VM
deletion, but the retained disk continues to incur charges until it is removed.

## 4. Configure Networking

The portal created:

- Virtual network: vnet-centralindia-2
- Subnet: snet-centralindia-1, 172.16.0.0/24
- Public IP: vm-assureai-prod-01-ip
- Network security group: nsg-assureai-prod
- Accelerated networking: enabled
- Load balancer: none

Select **Advanced** for the NIC network security group. Remove any default SSH rule
whose source is **Any**, then create:

| Priority | Name | Source | Protocol | Port | Action |
| ---: | --- | --- | --- | ---: | --- |
| 101 | Allow-SSH-MyIP | Your current public IPv4 with /32 | TCP | 22 | Allow |
| 110 | Allow-HTTP | Any | TCP | 80 | Allow |
| 120 | Allow-HTTPS | Any | TCP | 443 | Allow |

Port 443 was reserved for a possible later TLS setup but is not used by this HTTP-only
showcase. The SSH source IP used during creation was a single /32 address. If the ISP
changes that address, update the rule before reconnecting.

Never create public inbound rules for ports 5173, 8000, 5432, or 6379.

## 5. Configure Management, Monitoring, Advanced, and Tags

Management:

- System-assigned managed identity: off
- Microsoft Entra ID login: off
- Auto-shutdown: off
- Periodic assessment: on
- Patch orchestration: image default
- Hibernation: off

Monitoring:

- Recommended alert rules: off
- Boot diagnostics: enabled with managed storage
- OS guest diagnostics: off
- Application health monitoring: off

Advanced:

- Extensions: none
- VM applications: none
- Cloud-init/custom data: blank
- SQL Server: off
- Capacity reservation: none

Tags:

| Name | Value |
| --- | --- |
| Application | AssureAI |
| Environment | Demo |

Review the configuration, create the VM, download the private key, wait for the
deployment to complete, and open **Go to resource**. Confirm that the VM status is
**Running** and the Azure agent status is **Ready**.

## 6. Connect through SSH

From Windows PowerShell, replace the example key path and public IP if they differ:

    ssh -i "C:\Users\Admin\Downloads\assureai-prod-key.pem" azureuser@52.172.254.68

The original NSG rule permits this only from the configured public IP.

## 7. Update and prepare the 4 GiB VM

Run the following on the VM:

    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

Create 4 GiB of persistent swap for build-time memory spikes:

    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

Verify:

    free -h
    swapon --show

## 8. Install Docker Engine and Compose

Install from Docker's official Ubuntu repository:

    sudo apt-get install -y ca-certificates curl ufw
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
      | sudo tee /etc/apt/sources.list.d/docker.list

    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
      docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker azureuser
    sudo systemctl enable --now docker

Sign out and reconnect so the Docker group membership takes effect. Verify:

    docker --version
    docker compose version

## 9. Enable the host firewall

Azure NSG rules remain the external boundary. UFW provides a second host-level layer:

    sudo ufw allow OpenSSH
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw --force enable
    sudo ufw status

## 10. Resolve Azure container TLS timeouts

During this deployment, the VM host could reach PyPI immediately, but TLS handshakes
from Docker build containers timed out. TCP path-MTU probing fixed the problem:

    sudo sysctl -w net.ipv4.tcp_mtu_probing=1
    echo 'net.ipv4.tcp_mtu_probing=1' \
      | sudo tee /etc/sysctl.d/99-assureai-network.conf

This setting is only necessary when container TLS connections stall while equivalent
host requests work. Verify before applying it on another environment.

## 11. Put the source on the VM

The initial deployment transferred a secret-free source archive over SCP because the
production configuration had not yet been committed. After this guide is pushed, a
normal Git clone or pull can be used:

    sudo install -d -o azureuser -g azureuser /opt/assureai
    git clone <repository-url> /opt/assureai
    cd /opt/assureai

For an existing checkout:

    cd /opt/assureai
    git pull --ff-only origin main

Do not copy a populated environment file or SSH key into Git.

## 12. Generate production-only demo secrets

Create the untracked environment file directly on the VM:

    cd /opt/assureai
    umask 077
    postgres_password=$(openssl rand -hex 24)
    redis_password=$(openssl rand -hex 24)
    printf '%s\n' \
      'POSTGRES_DB=assureai' \
      'POSTGRES_USER=assureai' \
      "POSTGRES_PASSWORD=$postgres_password" \
      "REDIS_PASSWORD=$redis_password" \
      'ASSUREAI_PUBLIC_ORIGIN=http://52.172.254.68' \
      > .env.production
    chmod 600 .env.production

Never print, share, or commit the populated file.

## 13. Build and start frontend and backend

Validate the configuration:

    docker compose --env-file .env.production \
      -f docker-compose.prod.yml config --quiet

On the 4 GiB VM, build sequentially:

    export COMPOSE_PARALLEL_LIMIT=1
    docker compose --progress plain --env-file .env.production \
      -f docker-compose.prod.yml build api
    docker compose --progress plain --env-file .env.production \
      -f docker-compose.prod.yml build worker
    docker compose --progress plain --env-file .env.production \
      -f docker-compose.prod.yml build web

Start all services:

    docker compose --env-file .env.production \
      -f docker-compose.prod.yml up -d

The production configuration:

- builds React and serves static files with Nginx;
- proxies /api requests to FastAPI;
- publishes only Nginx on host port 80;
- keeps PostgreSQL, Redis, and FastAPI on the private Compose network;
- uses named volumes for PostgreSQL, Redis, and documents;
- runs one Dramatiq worker process with two threads;
- applies container memory limits appropriate for this demo VM.

## 14. Validate the live deployment

Check containers:

    docker compose --env-file .env.production \
      -f docker-compose.prod.yml ps

Expected services:

- assureai-prod-postgres-1: healthy
- assureai-prod-redis-1: healthy
- assureai-prod-api-1: healthy
- assureai-prod-worker-1: running
- assureai-prod-web-1: healthy

Check endpoints:

    curl -fsS http://127.0.0.1/
    curl -fsS http://127.0.0.1/health
    curl -fsS http://127.0.0.1/ready

The completed deployment was also checked through the public IP:

- <http://52.172.254.68/> returned HTTP 200.
- <http://52.172.254.68/ready> returned API status ready.
- A synthetic TXT document moved from QUEUED to READY.
- The worker created one deterministic chunk for that synthetic document.

The synthetic smoke-test project is named **Deployment Verification**.

## 15. Routine operations

View service state and recent logs:

    cd /opt/assureai
    docker compose --env-file .env.production \
      -f docker-compose.prod.yml ps
    docker compose --env-file .env.production \
      -f docker-compose.prod.yml logs --tail 100

Deploy a later version:

    cd /opt/assureai
    git pull --ff-only origin main
    export COMPOSE_PARALLEL_LIMIT=1
    docker compose --env-file .env.production \
      -f docker-compose.prod.yml up -d --build

Stop services without deleting data:

    docker compose --env-file .env.production \
      -f docker-compose.prod.yml stop

Do not run docker compose down with the -v option unless permanent deletion of the
database, Redis state, and uploaded documents is intended.

## 16. Current limitations

- No user authentication or authorization exists yet.
- Traffic is HTTP, not HTTPS.
- PostgreSQL and uploaded documents are on one VM.
- No automated volume backup is configured.
- The VM is a single point of failure.
- Local document storage is appropriate only for this single-host showcase.

These limitations are acceptable for the current demo but not for confidential or
production workloads.

## References

- [Create a Linux VM in the Azure Portal](https://learn.microsoft.com/azure/virtual-machines/linux/quick-create-portal?tabs=ubuntu)
- [Azure network security group guidance](https://learn.microsoft.com/azure/networking/design-guide/network-application-security-groups)
- [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Install the Docker Compose plugin](https://docs.docker.com/compose/install/linux/)
