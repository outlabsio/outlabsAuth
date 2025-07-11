import { createFileRoute } from "@tanstack/react-router";
import { AppSidebar } from "@/components/app-sidebar";
import { PageHeader } from "@/components/layout/page-header";
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmailSettings } from "@/components/settings/email-settings";
import { requireAuth } from "@/lib/route-guards";

export const Route = createFileRoute("/settings/")({
  beforeLoad: requireAuth,
  component: Settings,
});

function Settings() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <PageHeader 
          breadcrumbs={[
            { label: "Dashboard", href: "/dashboard" },
            { label: "Settings" }
          ]}
        />
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          <div className="mx-auto w-full max-w-6xl">
            <Tabs defaultValue="email" className="space-y-6">
              <TabsList>
                <TabsTrigger value="general">General</TabsTrigger>
                <TabsTrigger value="email">Email</TabsTrigger>
                <TabsTrigger value="security">Security</TabsTrigger>
                <TabsTrigger value="api">API Keys</TabsTrigger>
              </TabsList>

              <TabsContent value="general" className="space-y-6">
                <div className="rounded-lg border p-6">
                  <h2 className="text-lg font-semibold">General Settings</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    General system configuration options
                  </p>
                  <div className="mt-6 text-sm text-muted-foreground">
                    Coming soon...
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="email" className="space-y-6">
                <EmailSettings />
              </TabsContent>

              <TabsContent value="security" className="space-y-6">
                <div className="rounded-lg border p-6">
                  <h2 className="text-lg font-semibold">Security Settings</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    Configure security policies and authentication options
                  </p>
                  <div className="mt-6 text-sm text-muted-foreground">
                    Coming soon...
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="api" className="space-y-6">
                <div className="rounded-lg border p-6">
                  <h2 className="text-lg font-semibold">API Keys</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    Manage API keys for external integrations
                  </p>
                  <div className="mt-6 text-sm text-muted-foreground">
                    Coming soon...
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}