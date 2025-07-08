import { createFileRoute } from "@tanstack/react-router";
import { AppSidebar } from "@/components/app-sidebar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  BreadcrumbLink,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
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
        <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
          <div className="flex items-center gap-2 px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbLink href="/dashboard">Dashboard</BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage>Settings</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
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