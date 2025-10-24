"""
User Profile Models for Real Estate Platform

Demonstrates extending UserModel with Beanie Links for different user types:
- AgentProfile: For real estate agents (license, brokerage, specialties)
- CustomerProfile: For buyers/sellers (preferences, budget, saved searches)

See: docs-library/96-Extending-UserModel.md for complete documentation
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Literal
from beanie import Document, Link
from outlabs_auth.models.user import UserModel
from pydantic import Field


class AgentProfile(Document):
    """
    Real estate agent profile with licensing and performance data.

    Linked to UserModel via ExtendedUserModel.agent_profile.
    Only populated when user_type == "agent".
    """

    # Licensing Information
    license_number: str = Field(..., description="Real estate license number")
    license_state: str = Field(..., description="State where licensed (e.g., 'CA', 'TX')")
    brokerage_name: str = Field(..., description="Name of brokerage firm")

    # Experience & Specialization
    years_experience: int = Field(default=0, description="Years in real estate")
    specialties: List[str] = Field(
        default_factory=list,
        description="Specialties: ['residential', 'commercial', 'luxury', 'investment']"
    )

    # Professional Profile
    bio: str = Field(default="", description="Agent bio/description")
    certifications: List[str] = Field(
        default_factory=list,
        description="Additional certifications (CRS, ABR, GRI, etc.)"
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Languages spoken"
    )

    # Performance Metrics
    deals_closed: int = Field(default=0, description="Total deals closed")
    total_sales_volume: int = Field(default=0, description="Total sales volume in dollars")
    average_deal_size: int = Field(default=0, description="Average deal size")

    # Contact & Social
    phone_work: Optional[str] = None
    website: Optional[str] = None
    social_links: Dict[str, str] = Field(
        default_factory=dict,
        description="Social media links (linkedin, facebook, instagram, etc.)"
    )

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "agent_profiles"
        indexes = [
            "license_number",
            "license_state",
            "brokerage_name",
            [("specialties", 1)],
        ]

    def __repr__(self) -> str:
        return f"<AgentProfile(license={self.license_number}, brokerage={self.brokerage_name})>"


class TeamMemberProfile(Document):
    """
    Internal team member profile (support, admin, operations staff).

    Linked to UserModel via ExtendedUserModel.team_member_profile.
    Only populated when user_type == "team_member".
    """

    # Role & Department
    job_title: str = Field(default="", description="Job title")
    department: Literal["support", "operations", "marketing", "management", "it"] = Field(
        default="support",
        description="Department"
    )

    # Permissions & Access
    access_level: Literal["standard", "elevated", "full"] = Field(
        default="standard",
        description="Access level for internal tools"
    )
    can_view_all_leads: bool = Field(default=False, description="Can view leads across all entities")
    can_manage_entities: bool = Field(default=False, description="Can manage entity structure")

    # Work Information
    employee_id: Optional[str] = None
    hire_date: Optional[datetime] = None
    office_location: Optional[str] = None
    timezone: str = Field(default="America/Los_Angeles", description="User's timezone")

    # Contact
    phone_work: Optional[str] = None
    phone_extension: Optional[str] = None
    slack_id: Optional[str] = None

    # Skills & Responsibilities
    skills: List[str] = Field(
        default_factory=list,
        description="Skills/specializations (crm, reporting, training, etc.)"
    )
    responsibilities: List[str] = Field(
        default_factory=list,
        description="Primary responsibilities"
    )

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "team_member_profiles"
        indexes = [
            "department",
            "access_level",
            "employee_id",
        ]

    def __repr__(self) -> str:
        return f"<TeamMemberProfile(title={self.job_title}, dept={self.department})>"


class ExtendedUserModel(UserModel):
    """
    Extended UserModel with profile links for different user types.

    Supports three user types:
    - agent: Real estate agent with AgentProfile
    - team_member: Internal staff with TeamMemberProfile
    - admin: System admin with no profile

    Only ONE profile link will be populated based on user_type.

    Example:
        >>> user = await ExtendedUserModel.find_one(email="agent@example.com")
        >>> user.user_type
        'agent'
        >>> profile = await user.get_profile()
        >>> profile.license_number
        'RE123456'
    """

    # User Type (determines which profile to use)
    user_type: Literal["agent", "team_member", "admin"] = Field(
        default="team_member",
        description="User type determines which profile link is used"
    )

    # Profile Links (only one populated based on user_type)
    agent_profile: Optional[Link[AgentProfile]] = Field(
        default=None,
        description="Agent profile (only for user_type='agent')"
    )
    team_member_profile: Optional[Link[TeamMemberProfile]] = Field(
        default=None,
        description="Team member profile (only for user_type='team_member')"
    )

    class Settings:
        name = "users"  # Same collection as UserModel
        indexes = [
            "user_type",  # Filter by user type
        ]

    async def get_profile(self) -> Optional[Document]:
        """
        Get the appropriate profile based on user type.

        After calling this method, the profile link is replaced with the actual
        document and can be accessed directly via user.agent_profile or
        user.team_member_profile.

        Returns:
            AgentProfile, TeamMemberProfile, or None (for admins)

        Example:
            >>> user = await ExtendedUserModel.find_one(email="user@example.com")
            >>> profile = await user.get_profile()
            >>> if profile:
            ...     print(profile.model_dump())
            >>> # Or access via the link field directly after fetch
            >>> if user.agent_profile:
            ...     print(user.agent_profile.license_number)
        """
        # Fetch all links at once (this replaces Link objects with actual documents)
        await self.fetch_all_links()

        # Return the appropriate profile
        if self.user_type == "agent":
            return self.agent_profile
        elif self.user_type == "team_member":
            return self.team_member_profile
        return None

    async def create_profile_for_type(self) -> Optional[Document]:
        """
        Create appropriate profile based on user type.

        Called after user registration to auto-create profile.
        Admins don't get profiles.

        Returns:
            Created profile or None (for admins)

        Example:
            >>> user = ExtendedUserModel(email="new@example.com", user_type="agent")
            >>> await user.save()
            >>> profile = await user.create_profile_for_type()
            >>> profile.license_number = "RE123456"
            >>> await profile.save()
        """
        if self.user_type == "agent":
            # Create empty agent profile
            profile = AgentProfile(
                license_number="",
                license_state="",
                brokerage_name="",
                years_experience=0,
                specialties=[],
                bio="",
                certifications=[],
                languages=[]
            )
            await profile.save()
            self.agent_profile = profile

        elif self.user_type == "team_member":
            # Create empty team member profile
            profile = TeamMemberProfile(
                job_title="",
                department="support",
                access_level="standard",
                skills=[],
                responsibilities=[]
            )
            await profile.save()
            self.team_member_profile = profile

        else:
            # Admins don't have profiles
            return None

        await self.save()
        return profile

    async def has_profile(self) -> bool:
        """
        Check if user has a profile.

        Returns:
            True if profile exists for user type

        Example:
            >>> if not await user.has_profile():
            ...     await user.create_profile_for_type()
        """
        if self.user_type == "agent":
            return self.agent_profile is not None
        elif self.user_type == "team_member":
            return self.team_member_profile is not None
        return False  # Admins have no profile

    def __repr__(self) -> str:
        return f"<ExtendedUserModel(email={self.email}, user_type={self.user_type})>"
