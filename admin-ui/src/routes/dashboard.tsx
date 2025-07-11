import { createFileRoute } from "@tanstack/react-router";
import { PageLayout } from "@/components/layout/page-layout";
import { PageTitle } from "@/components/ui/page-title";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Users, Shield, Building2, Activity, TrendingUp, Clock, Key, Monitor } from "lucide-react";
import { requireAuth } from "@/lib/route-guards";
import { generateAuthMetrics } from "@/lib/mock-data/auth-metrics";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { Area, AreaChart, Bar, BarChart, Line, LineChart, Pie, PieChart, Cell, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts";

export const Route = createFileRoute("/dashboard")({
  beforeLoad: requireAuth,
  component: Dashboard,
});

function Dashboard() {
  const metrics = generateAuthMetrics();
  
  return (
    <PageLayout
      breadcrumbs={[
        { label: "Dashboard" }
      ]}
    >
      <PageTitle 
        title="Dashboard"
        description="Monitor your authentication system performance and usage"
      />
      
      {/* Key Metrics */}
      <div className='grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-6'>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Total Users</CardTitle>
            <Users className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{metrics.summaryStats.totalUsers.toLocaleString()}</div>
            <p className='text-xs text-muted-foreground'>
              +{metrics.summaryStats.newUsersToday} today
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Active Sessions</CardTitle>
            <Activity className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{metrics.realtimeMetrics.activeSessions.toLocaleString()}</div>
            <p className='text-xs text-muted-foreground'>
              {metrics.realtimeMetrics.activeUsers} users online
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Success Rate</CardTitle>
            <Shield className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{metrics.summaryStats.loginSuccessRate}</div>
            <p className='text-xs text-muted-foreground'>Login attempts</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Avg Response</CardTitle>
            <Clock className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{metrics.realtimeMetrics.avgResponseTime}</div>
            <p className='text-xs text-muted-foreground'>{metrics.realtimeMetrics.apiCallsPerMinute} req/min</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 1 */}
      <div className='grid gap-4 md:grid-cols-2 lg:grid-cols-7 mb-6'>
        <Card className='col-span-4'>
          <CardHeader>
            <CardTitle>Daily Active Users</CardTitle>
            <CardDescription>User activity over the last 30 days</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={{
              users: {
                label: "Active Users",
                color: "hsl(var(--chart-1))",
              },
            }}>
              <AreaChart data={metrics.dauData} height={300}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis 
                  dataKey="date" 
                  tickFormatter={(value) => new Date(value).toLocaleDateString('default', { day: 'numeric', month: 'short' })}
                  className="text-xs"
                />
                <YAxis className="text-xs" />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Area 
                  type="monotone" 
                  dataKey="users" 
                  stroke="hsl(var(--chart-1))" 
                  fill="hsl(var(--chart-1))" 
                  fillOpacity={0.2}
                />
              </AreaChart>
            </ChartContainer>
          </CardContent>
        </Card>
        
        <Card className='col-span-3'>
          <CardHeader>
            <CardTitle>Login Attempts</CardTitle>
            <CardDescription>Success vs Failed attempts (7 days)</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={{
              successful: {
                label: "Successful",
                color: "hsl(var(--chart-2))",
              },
              failed: {
                label: "Failed",
                color: "hsl(var(--destructive))",
              },
            }}>
              <BarChart data={metrics.loginAttemptsData} height={300}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="date" className="text-xs" />
                <YAxis className="text-xs" />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Bar dataKey="successful" fill="hsl(var(--chart-2))" radius={[4, 4, 0, 0]} />
                <Bar dataKey="failed" fill="hsl(var(--destructive))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className='grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-6'>
        <Card>
          <CardHeader>
            <CardTitle>Authentication Methods</CardTitle>
            <CardDescription>Distribution of auth methods used</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={{
              password: { label: "Password", color: "hsl(var(--chart-1))" },
              sso: { label: "SSO", color: "hsl(var(--chart-2))" },
              oauth: { label: "OAuth", color: "hsl(var(--chart-3))" },
              biometric: { label: "Biometric", color: "hsl(var(--chart-4))" },
            }}>
              <PieChart width={300} height={300}>
                <Pie
                  data={metrics.authMethodsData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ percentage }) => `${percentage}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="count"
                >
                  {metrics.authMethodsData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={`hsl(var(--chart-${index + 1}))`} />
                  ))}
                </Pie>
                <ChartTooltip content={<ChartTooltipContent />} />
              </PieChart>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Monthly Active Users</CardTitle>
            <CardDescription>MAU trend over 6 months</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={{
              users: {
                label: "Users",
                color: "hsl(var(--chart-1))",
              },
            }}>
              <LineChart data={metrics.mauData} height={300}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="month" className="text-xs" />
                <YAxis className="text-xs" />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Line 
                  type="monotone" 
                  dataKey="users" 
                  stroke="hsl(var(--chart-1))" 
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Platform Usage</CardTitle>
            <CardDescription>Users by platform type</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {metrics.platformUsageData.map((platform) => (
                <div key={platform.platform} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Monitor className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">{platform.platform}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">{platform.users.toLocaleString()}</span>
                    <span className="text-xs text-muted-foreground">({platform.percentage}%)</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Common administrative tasks</CardDescription>
        </CardHeader>
        <CardContent>
          <div className='grid gap-2 md:grid-cols-4'>
            <Button variant='outline' className='justify-start'>
              <Users className='mr-2 h-4 w-4' />
              Create New User
            </Button>
            <Button variant='outline' className='justify-start'>
              <Shield className='mr-2 h-4 w-4' />
              Manage Roles
            </Button>
            <Button variant='outline' className='justify-start'>
              <Key className='mr-2 h-4 w-4' />
              View API Keys
            </Button>
            <Button variant='outline' className='justify-start'>
              <Activity className='mr-2 h-4 w-4' />
              Activity Logs
            </Button>
          </div>
        </CardContent>
      </Card>
    </PageLayout>
  );
}
