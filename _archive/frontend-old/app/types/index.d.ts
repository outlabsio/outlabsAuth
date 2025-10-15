import type { AvatarProps as UIAvatarProps } from "@nuxt/ui";

export type UserStatus = "subscribed" | "unsubscribed" | "bounced";
export type SaleStatus = "paid" | "failed" | "refunded";

export interface User {
  id: number;
  _id?: string;
  name: string;
  email: string;
  avatar?: UIAvatarProps;
  status?: UserStatus;
  location?: string;
  is_active?: boolean;
  is_verified?: boolean;
  is_superuser?: boolean;
  is_team_member?: boolean;
  last_login?: string;
  created_at?: string;
  permissions?: string[];
}

export interface Mail {
  id: number;
  unread?: boolean;
  from: User;
  subject: string;
  body: string;
  date: string;
}

export interface Member {
  name: string;
  username: string;
  role: "member" | "owner";
  avatar: Avatar;
}

export interface Stat {
  title: string;
  icon: string;
  value: number | string;
  variation: number;
  formatter?: (value: number) => string;
}

export interface Sale {
  id: string;
  date: string;
  status: SaleStatus;
  email: string;
  amount: number;
}

export interface Notification {
  id: number;
  unread?: boolean;
  sender: User;
  body: string;
  date: string;
}

export type Period = "daily" | "weekly" | "monthly";

export interface Range {
  start: Date;
  end: Date;
}

// Re-export AvatarProps from Nuxt UI for use elsewhere
export type AvatarProps = UIAvatarProps;
