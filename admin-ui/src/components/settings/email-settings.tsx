import { useForm } from "@tanstack/react-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Loader2, Mail } from "lucide-react";
import { toast } from "sonner";
import { authenticatedFetch } from "@/lib/auth";

interface EmailSettings {
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password: string;
  use_tls: boolean;
  from_email: string;
  from_name: string;
}

interface CurrentUser {
  email: string;
  first_name: string;
  last_name: string;
}

// API functions
async function fetchEmailSettings(): Promise<EmailSettings> {
  const response = await authenticatedFetch("/v1/settings/email");
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to fetch email settings");
  }
  return response.json();
}

async function updateEmailSettings(settings: EmailSettings): Promise<void> {
  const response = await authenticatedFetch("/v1/settings/email", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(settings),
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to update email settings");
  }
}

async function sendTestEmail(): Promise<{ message: string }> {
  const response = await authenticatedFetch("/v1/settings/email/test", {
    method: "POST",
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to send test email");
  }
  return response.json();
}

async function fetchCurrentUser(): Promise<CurrentUser> {
  const response = await authenticatedFetch("/v1/auth/me");
  if (!response.ok) throw new Error("Failed to fetch user info");
  return response.json();
}

export function EmailSettings() {
  const queryClient = useQueryClient();

  // Fetch current settings
  const { data: settings, isLoading } = useQuery({
    queryKey: ["emailSettings"],
    queryFn: fetchEmailSettings,
  });

  // Fetch current user
  const { data: currentUser } = useQuery({
    queryKey: ["currentUser"],
    queryFn: fetchCurrentUser,
  });

  // Update settings mutation
  const updateMutation = useMutation({
    mutationFn: updateEmailSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["emailSettings"] });
      toast.success("Email settings updated successfully!");
    },
    onError: (error: Error) => {
      toast.error(`Failed to update settings: ${error.message}`);
    },
  });

  // Test email mutation
  const testMutation = useMutation({
    mutationFn: sendTestEmail,
    onSuccess: (data) => {
      toast.success(data.message || "Test email sent successfully!");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to send test email");
    },
  });

  const form = useForm({
    defaultValues: settings || {
      smtp_host: "",
      smtp_port: 587,
      smtp_user: "",
      smtp_password: "",
      use_tls: true,
      from_email: "",
      from_name: "",
    },
    onSubmit: async ({ value }) => {
      await updateMutation.mutateAsync(value);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Email Configuration</CardTitle>
          <CardDescription>
            Configure SMTP settings for system email notifications. These settings are used for
            administrator password resets and security alerts.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              e.stopPropagation();
              form.handleSubmit();
            }}
            className="space-y-6"
          >
            <div className="grid gap-4 md:grid-cols-2">
              <form.Field
                name="smtp_host"
                validators={{
                  onChange: ({ value }) => (!value ? "SMTP host is required" : undefined),
                }}
              >
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="smtp_host">SMTP Host</Label>
                    <Input
                      id="smtp_host"
                      placeholder="smtp.gmail.com"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                    />
                    {field.state.meta.errors ? (
                      <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                    ) : null}
                  </div>
                )}
              </form.Field>

              <form.Field
                name="smtp_port"
                validators={{
                  onChange: ({ value }) => {
                    if (!value) return "SMTP port is required";
                    if (value < 1 || value > 65535) return "Invalid port number";
                    return undefined;
                  },
                }}
              >
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="smtp_port">SMTP Port</Label>
                    <Input
                      id="smtp_port"
                      type="number"
                      placeholder="587"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(parseInt(e.target.value) || 0)}
                      onBlur={field.handleBlur}
                    />
                    {field.state.meta.errors ? (
                      <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                    ) : null}
                  </div>
                )}
              </form.Field>

              <form.Field
                name="smtp_user"
                validators={{
                  onChange: ({ value }) => (!value ? "SMTP username is required" : undefined),
                }}
              >
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="smtp_user">SMTP Username</Label>
                    <Input
                      id="smtp_user"
                      placeholder="your-email@gmail.com"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                    />
                    {field.state.meta.errors ? (
                      <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                    ) : null}
                  </div>
                )}
              </form.Field>

              <form.Field name="smtp_password">
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="smtp_password">SMTP Password</Label>
                    <Input
                      id="smtp_password"
                      type="password"
                      placeholder="••••••••"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                    />
                    <p className="text-xs text-muted-foreground">
                      Leave blank to keep existing password
                    </p>
                  </div>
                )}
              </form.Field>

              <form.Field
                name="from_email"
                validators={{
                  onChange: ({ value }) => {
                    if (!value) return "From email is required";
                    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return "Invalid email format";
                    return undefined;
                  },
                }}
              >
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="from_email">From Email</Label>
                    <Input
                      id="from_email"
                      type="email"
                      placeholder="noreply@yourdomain.com"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                    />
                    {field.state.meta.errors ? (
                      <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                    ) : null}
                  </div>
                )}
              </form.Field>

              <form.Field
                name="from_name"
                validators={{
                  onChange: ({ value }) => (!value ? "From name is required" : undefined),
                }}
              >
                {(field) => (
                  <div className="space-y-2">
                    <Label htmlFor="from_name">From Name</Label>
                    <Input
                      id="from_name"
                      placeholder="Outlabs Auth System"
                      value={field.state.value}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                    />
                    {field.state.meta.errors ? (
                      <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                    ) : null}
                  </div>
                )}
              </form.Field>
            </div>

            <form.Field name="use_tls">
              {(field) => (
                <div className="flex items-center space-x-2">
                  <Switch
                    id="use_tls"
                    checked={field.state.value}
                    onCheckedChange={field.handleChange}
                  />
                  <Label htmlFor="use_tls">Use TLS/STARTTLS</Label>
                </div>
              )}
            </form.Field>

            <div className="flex justify-end space-x-2">
              <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
                {([canSubmit, isSubmitting]) => (
                  <Button
                    type="submit"
                    disabled={!canSubmit || isSubmitting || updateMutation.isPending}
                  >
                    {updateMutation.isPending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      "Save Settings"
                    )}
                  </Button>
                )}
              </form.Subscribe>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Test Email</CardTitle>
          <CardDescription>
            Send a test email to verify your configuration is working correctly.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="flex items-center space-x-3">
                <Mail className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Test Email Recipient</p>
                  <p className="text-sm text-muted-foreground">
                    {currentUser?.email || "Loading..."}
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending}
              >
                {testMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Sending...
                  </>
                ) : (
                  "Send Test Email"
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}