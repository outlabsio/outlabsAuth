"use client"

import * as React from "react"
import {
  Building2,
  Globe,
  Home,
  Settings2,
  Shield,
  Users,
  Activity,
} from "lucide-react"

import { NavMain } from "@/components/nav-main"
import { NavUser } from "@/components/nav-user"
import { TeamSwitcher } from "@/components/team-switcher"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"

// Navigation data structured for Outlabs Auth
const data = {
  user: {
    name: "System Admin",
    email: "system@outlabs.io",
    avatar: "",
  },
  navMain: [
    {
      title: "Dashboard",
      url: "/dashboard",
      icon: Home,
      isActive: true,
    },
    {
      title: "User Management",
      url: "#",
      icon: Users,
      items: [
        {
          title: "All Users",
          url: "/users",
        },
        {
          title: "User Groups",
          url: "/users/groups",
        },
        {
          title: "Invitations",
          url: "/users/invitations",
        },
      ],
    },
    {
      title: "Access Control",
      url: "#",
      icon: Shield,
      items: [
        {
          title: "Roles",
          url: "/roles",
        },
        {
          title: "Permissions",
          url: "/permissions",
        },
        {
          title: "Policies",
          url: "/policies",
        },
      ],
    },
    {
      title: "Platforms",
      url: "#",
      icon: Globe,
      items: [
        {
          title: "All Platforms",
          url: "/platforms",
        },
        {
          title: "Client Accounts",
          url: "/clients",
        },
        {
          title: "Billing",
          url: "/billing",
        },
      ],
    },
    {
      title: "Monitoring",
      url: "#",
      icon: Activity,
      items: [
        {
          title: "Audit Logs",
          url: "/audit",
        },
        {
          title: "Analytics",
          url: "/analytics",
        },
        {
          title: "Security Events",
          url: "/security",
        },
      ],
    },
    {
      title: "Settings",
      url: "#",
      icon: Settings2,
      items: [
        {
          title: "General",
          url: "/settings",
        },
        {
          title: "Security",
          url: "/settings/security",
        },
        {
          title: "API Keys",
          url: "/settings/api-keys",
        },
        {
          title: "Webhooks",
          url: "/settings/webhooks",
        },
      ],
    },
  ],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <TeamSwitcher />
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={data.user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}