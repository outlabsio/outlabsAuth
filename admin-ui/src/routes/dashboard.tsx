import { createFileRoute } from "@tanstack/react-router";
import { AppSidebar } from "@/components/app-sidebar";
import { Breadcrumb, BreadcrumbItem, BreadcrumbList, BreadcrumbPage } from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Users, Shield, Building2, Activity } from "lucide-react";
import { requireAuth } from "@/lib/route-guards";

export const Route = createFileRoute("/dashboard")({
  beforeLoad: requireAuth,
  component: Dashboard,
});

function Dashboard() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className='flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12'>
          <div className='flex items-center gap-2 px-4'>
            <SidebarTrigger className='-ml-1' />
            <Separator orientation='vertical' className='mr-2 h-4' />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbPage>Dashboard</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        <div className='flex flex-1 flex-col gap-4 p-4 pt-0'>
          <div className='grid gap-4 md:grid-cols-2 lg:grid-cols-4'>
            <Card>
              <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                <CardTitle className='text-sm font-medium'>Total Users</CardTitle>
                <Users className='h-4 w-4 text-muted-foreground' />
              </CardHeader>
              <CardContent>
                <div className='text-2xl font-bold'>1</div>
                <p className='text-xs text-muted-foreground'>System administrator</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                <CardTitle className='text-sm font-medium'>Active Roles</CardTitle>
                <Shield className='h-4 w-4 text-muted-foreground' />
              </CardHeader>
              <CardContent>
                <div className='text-2xl font-bold'>1</div>
                <p className='text-xs text-muted-foreground'>Super Admin role</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                <CardTitle className='text-sm font-medium'>Client Accounts</CardTitle>
                <Building2 className='h-4 w-4 text-muted-foreground' />
              </CardHeader>
              <CardContent>
                <div className='text-2xl font-bold'>0</div>
                <p className='text-xs text-muted-foreground'>No clients yet</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                <CardTitle className='text-sm font-medium'>System Status</CardTitle>
                <Activity className='h-4 w-4 text-muted-foreground' />
              </CardHeader>
              <CardContent>
                <div className='text-2xl font-bold'>Active</div>
                <p className='text-xs text-muted-foreground'>All systems operational</p>
              </CardContent>
            </Card>
          </div>

          <div className='grid gap-4 md:grid-cols-2 lg:grid-cols-7'>
            <Card className='col-span-4'>
              <CardHeader>
                <CardTitle>Welcome to Outlabs Auth</CardTitle>
                <CardDescription>Enterprise-grade Role-Based Access Control (RBAC) authentication platform</CardDescription>
              </CardHeader>
              <CardContent>
                <div className='space-y-4'>
                  <div>
                    <h3 className='font-semibold mb-2'>Quick Actions</h3>
                    <div className='grid gap-2 md:grid-cols-2'>
                      <Button variant='outline' className='justify-start'>
                        <Users className='mr-2 h-4 w-4' />
                        Create New User
                      </Button>
                      <Button variant='outline' className='justify-start'>
                        <Shield className='mr-2 h-4 w-4' />
                        Manage Roles
                      </Button>
                      <Button variant='outline' className='justify-start'>
                        <Building2 className='mr-2 h-4 w-4' />
                        Add Client Account
                      </Button>
                      <Button variant='outline' className='justify-start'>
                        <Activity className='mr-2 h-4 w-4' />
                        View Audit Logs
                      </Button>
                    </div>
                  </div>
                  <div>
                    <h3 className='font-semibold mb-2'>Getting Started</h3>
                    <p className='text-sm text-muted-foreground'>
                      You've successfully initialized the platform with a super administrator account. Start by creating users, defining roles, and setting up client accounts to build your access
                      control system.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className='col-span-3'>
              <CardHeader>
                <CardTitle>Recent Activity</CardTitle>
                <CardDescription>Latest system events</CardDescription>
              </CardHeader>
              <CardContent>
                <div className='space-y-4'>
                  <div className='flex items-center'>
                    <div className='ml-4 space-y-1'>
                      <p className='text-sm font-medium leading-none'>Platform Initialized</p>
                      <p className='text-sm text-muted-foreground'>Super admin account created</p>
                    </div>
                    <div className='ml-auto font-medium text-sm'>Just now</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
