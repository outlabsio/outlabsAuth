"""
OutlabsAuth CLI Tool

Command-line interface for common authentication and authorization tasks.

Usage:
    python -m outlabs_auth.cli init --preset simple
    python -m outlabs_auth.cli create-role --name admin --permissions "*:*"
    python -m outlabs_auth.cli create-user --email admin@example.com
    python -m outlabs_auth.cli list-roles
    python -m outlabs_auth.cli benchmark

Requirements:
    - MongoDB connection
    - Beanie initialized
"""
import asyncio
import sys
import time
from typing import Optional, List
from datetime import datetime

import click
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

from outlabs_auth import SimpleRBAC, EnterpriseRBAC
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.entity import EntityModel, EntityClass
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.closure import EntityClosureModel


console = Console()


# ============================================================================
# Helper Functions
# ============================================================================

async def connect_database(mongodb_url: str, database_name: str):
    """Connect to MongoDB and initialize Beanie"""
    client = AsyncIOMotorClient(mongodb_url)
    database = client[database_name]

    await init_beanie(
        database=database,
        document_models=[
            UserModel,
            RoleModel,
            EntityModel,
            EntityMembershipModel,
            EntityClosureModel,
        ]
    )

    return client


def create_auth_instance(preset: str, secret_key: str, redis_url: Optional[str] = None):
    """Create auth instance based on preset"""
    config = AuthConfig(
        secret_key=secret_key,
        algorithm="HS256",
    )

    if preset == "simple":
        return SimpleRBAC(config=config)
    elif preset == "enterprise":
        return EnterpriseRBAC(config=config)
    else:
        raise ValueError(f"Unknown preset: {preset}")


# ============================================================================
# CLI Commands
# ============================================================================

@click.group()
def cli():
    """OutlabsAuth CLI - Manage authentication and authorization"""
    pass


@cli.command()
@click.option("--preset", type=click.Choice(["simple", "enterprise"]), required=True, help="Auth preset")
@click.option("--mongodb-url", default="mongodb://localhost:27017", help="MongoDB connection string")
@click.option("--database", default="outlabs_auth", help="Database name")
@click.option("--secret-key", required=True, help="JWT secret key")
async def init(preset: str, mongodb_url: str, database: str, secret_key: str):
    """Initialize OutlabsAuth with a preset"""
    console.print(f"[bold blue]Initializing OutlabsAuth with {preset} preset...[/bold blue]")

    try:
        client = await connect_database(mongodb_url, database)
        auth = create_auth_instance(preset, secret_key)
        await auth.initialize()

        console.print(f"[bold green]✓ Successfully initialized {preset.upper()} preset[/bold green]")
        console.print(f"  Database: {database}")
        console.print(f"  Preset: {preset}")

        client.close()

    except Exception as e:
        console.print(f"[bold red]✗ Initialization failed: {e}[/bold red]")
        sys.exit(1)


@cli.command()
@click.option("--name", required=True, help="Role name")
@click.option("--display-name", help="Display name")
@click.option("--permissions", multiple=True, help="Permissions (can specify multiple)")
@click.option("--mongodb-url", default="mongodb://localhost:27017")
@click.option("--database", default="outlabs_auth")
@click.option("--secret-key", required=True)
@click.option("--preset", type=click.Choice(["simple", "enterprise"]), default="simple")
async def create_role(
    name: str,
    display_name: Optional[str],
    permissions: tuple,
    mongodb_url: str,
    database: str,
    secret_key: str,
    preset: str,
):
    """Create a new role"""
    console.print(f"[bold blue]Creating role: {name}[/bold blue]")

    try:
        client = await connect_database(mongodb_url, database)
        auth = create_auth_instance(preset, secret_key)

        role = await auth.role_service.create_role(
            name=name,
            display_name=display_name or name.replace("_", " ").title(),
            description=f"Role: {name}",
            permissions=list(permissions),
            is_global=True,
        )

        console.print(f"[bold green]✓ Role created successfully[/bold green]")
        console.print(f"  ID: {role.id}")
        console.print(f"  Name: {role.name}")
        console.print(f"  Permissions: {', '.join(role.permissions)}")

        client.close()

    except Exception as e:
        console.print(f"[bold red]✗ Failed to create role: {e}[/bold red]")
        sys.exit(1)


@cli.command()
@click.option("--email", required=True, help="User email")
@click.option("--username", required=True, help="Username")
@click.option("--password", required=True, prompt=True, hide_input=True, help="Password")
@click.option("--full-name", help="Full name")
@click.option("--role", help="Role name to assign")
@click.option("--mongodb-url", default="mongodb://localhost:27017")
@click.option("--database", default="outlabs_auth")
@click.option("--secret-key", required=True)
@click.option("--preset", type=click.Choice(["simple", "enterprise"]), default="simple")
async def create_user(
    email: str,
    username: str,
    password: str,
    full_name: Optional[str],
    role: Optional[str],
    mongodb_url: str,
    database: str,
    secret_key: str,
    preset: str,
):
    """Create a new user"""
    console.print(f"[bold blue]Creating user: {email}[/bold blue]")

    try:
        client = await connect_database(mongodb_url, database)
        auth = create_auth_instance(preset, secret_key)

        user = await auth.user_service.create_user(
            email=email,
            username=username,
            password=password,
            full_name=full_name or username,
        )

        # Assign role if specified
        if role:
            role_obj = await auth.role_service.find_by_name(role)
            if role_obj:
                user.role_ids = [role_obj.id]
                await user.save()
                console.print(f"  Assigned role: {role}")

        console.print(f"[bold green]✓ User created successfully[/bold green]")
        console.print(f"  ID: {user.id}")
        console.print(f"  Email: {user.email}")
        console.print(f"  Username: {user.username}")

        client.close()

    except Exception as e:
        console.print(f"[bold red]✗ Failed to create user: {e}[/bold red]")
        sys.exit(1)


@cli.command()
@click.option("--mongodb-url", default="mongodb://localhost:27017")
@click.option("--database", default="outlabs_auth")
async def list_roles(mongodb_url: str, database: str):
    """List all roles"""
    try:
        client = await connect_database(mongodb_url, database)

        roles = await RoleModel.find_all().to_list()

        if not roles:
            console.print("[yellow]No roles found[/yellow]")
            client.close()
            return

        table = Table(title="Roles")
        table.add_column("Name", style="cyan")
        table.add_column("Display Name", style="green")
        table.add_column("Permissions", style="yellow")
        table.add_column("Global", style="magenta")

        for role in roles:
            table.add_row(
                role.name,
                role.display_name,
                ", ".join(role.permissions[:3]) + ("..." if len(role.permissions) > 3 else ""),
                "✓" if role.is_global else "✗",
            )

        console.print(table)
        console.print(f"\n[bold]Total: {len(roles)} roles[/bold]")

        client.close()

    except Exception as e:
        console.print(f"[bold red]✗ Failed to list roles: {e}[/bold red]")
        sys.exit(1)


@cli.command()
@click.option("--mongodb-url", default="mongodb://localhost:27017")
@click.option("--database", default="outlabs_auth")
async def list_users(mongodb_url: str, database: str):
    """List all users"""
    try:
        client = await connect_database(mongodb_url, database)

        users = await UserModel.find_all().to_list()

        if not users:
            console.print("[yellow]No users found[/yellow]")
            client.close()
            return

        table = Table(title="Users")
        table.add_column("Email", style="cyan")
        table.add_column("Username", style="green")
        table.add_column("Full Name", style="yellow")
        table.add_column("Status", style="magenta")
        table.add_column("Roles", style="blue")

        for user in users:
            role_count = len(user.role_ids) if user.role_ids else 0
            table.add_row(
                user.email,
                user.username,
                user.full_name or "-",
                user.status.value,
                str(role_count),
            )

        console.print(table)
        console.print(f"\n[bold]Total: {len(users)} users[/bold]")

        client.close()

    except Exception as e:
        console.print(f"[bold red]✗ Failed to list users: {e}[/bold red]")
        sys.exit(1)


@cli.command()
@click.option("--mongodb-url", default="mongodb://localhost:27017")
@click.option("--database", default="outlabs_auth")
@click.option("--secret-key", required=True)
@click.option("--preset", type=click.Choice(["simple", "enterprise"]), default="enterprise")
async def benchmark(mongodb_url: str, database: str, secret_key: str, preset: str):
    """Run performance benchmarks"""
    console.print("[bold blue]Running OutlabsAuth Performance Benchmarks[/bold blue]\n")

    try:
        client = await connect_database(mongodb_url, database)
        auth = create_auth_instance(preset, secret_key)
        await auth.initialize()

        results = {}

        # Benchmark 1: User creation
        console.print("[cyan]1. User Creation...[/cyan]")
        start = time.perf_counter()
        for i in range(10):
            await auth.user_service.create_user(
                email=f"bench_user_{i}_{datetime.now().timestamp()}@example.com",
                username=f"bench_{i}",
                password="TestPass123!",
                full_name=f"Bench User {i}",
            )
        elapsed = (time.perf_counter() - start) / 10
        results["user_creation"] = elapsed * 1000
        console.print(f"   Average: {elapsed * 1000:.2f}ms per user\n")

        # Benchmark 2: Role creation
        console.print("[cyan]2. Role Creation...[/cyan]")
        start = time.perf_counter()
        for i in range(10):
            await auth.role_service.create_role(
                name=f"bench_role_{i}_{datetime.now().timestamp()}",
                display_name=f"Bench Role {i}",
                description="Benchmark role",
                permissions=["test:read", "test:write"],
                is_global=True,
            )
        elapsed = (time.perf_counter() - start) / 10
        results["role_creation"] = elapsed * 1000
        console.print(f"   Average: {elapsed * 1000:.2f}ms per role\n")

        # Benchmark 3: Permission check (if EnterpriseRBAC)
        if preset == "enterprise":
            console.print("[cyan]3. Permission Check (Enterprise)...[/cyan]")

            # Create test entity and user
            entity = await auth.entity_service.create_entity(
                name=f"bench_entity_{datetime.now().timestamp()}",
                display_name="Bench Entity",
                entity_class=EntityClass.STRUCTURAL,
                entity_type="department",
            )

            user = await auth.user_service.create_user(
                email=f"perm_test_{datetime.now().timestamp()}@example.com",
                username="perm_test",
                password="TestPass123!",
            )

            role = await auth.role_service.create_role(
                name=f"perm_role_{datetime.now().timestamp()}",
                display_name="Permission Test Role",
                description="Test role",
                permissions=["test:read"],
                is_global=False,
            )

            await auth.membership_service.add_member(
                entity_id=str(entity.id),
                user_id=str(user.id),
                role_ids=[str(role.id)],
            )

            # Benchmark permission check
            start = time.perf_counter()
            for _ in range(100):
                await auth.permission_service.check_permission(
                    user_id=str(user.id),
                    permission="test:read",
                    entity_id=str(entity.id),
                )
            elapsed = (time.perf_counter() - start) / 100
            results["permission_check"] = elapsed * 1000
            console.print(f"   Average: {elapsed * 1000:.3f}ms per check\n")

        # Display summary
        console.print("\n[bold green]Benchmark Results Summary:[/bold green]")
        table = Table()
        table.add_column("Operation", style="cyan")
        table.add_column("Average Time", style="yellow")
        table.add_column("Operations/sec", style="green")

        for operation, time_ms in results.items():
            ops_per_sec = 1000 / time_ms if time_ms > 0 else 0
            table.add_row(
                operation.replace("_", " ").title(),
                f"{time_ms:.3f}ms",
                f"{ops_per_sec:.0f}",
            )

        console.print(table)

        client.close()

    except Exception as e:
        console.print(f"[bold red]✗ Benchmark failed: {e}[/bold red]")
        sys.exit(1)


# ============================================================================
# Main
# ============================================================================

def main():
    """Main entry point"""
    # Make all commands async-compatible
    for command in cli.commands.values():
        if asyncio.iscoroutinefunction(command.callback):
            original_callback = command.callback
            command.callback = lambda *args, **kwargs: asyncio.run(original_callback(*args, **kwargs))

    cli()


if __name__ == "__main__":
    main()
