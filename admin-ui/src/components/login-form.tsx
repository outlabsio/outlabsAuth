import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { toast } from "sonner";

async function handleLogin(values: { username: string; password: string }) {
  const response = await fetch("/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(values),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Login failed");
  }

  const data = await response.json();
  return data;
}

export function LoginForm({ className, ...props }: React.ComponentProps<"div">) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const login = useAuthStore((state) => state.login);

  const mutation = useMutation({
    mutationFn: handleLogin,
    onSuccess: async (data) => {
      // Store tokens in Zustand store
      await login(data);
      
      queryClient.invalidateQueries({ queryKey: ["user"] });
      toast.success("Login successful!");
      router.navigate({ to: "/dashboard" });
    },
    onError: (error: Error) => {
      toast.error(error.message || "Login failed");
    },
  });

  const form = useForm({
    defaultValues: {
      username: "",
      password: "",
    },
    onSubmit: async ({ value }) => {
      mutation.mutate(value);
    },
  });

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card>
        <CardHeader className='text-center'>
          <CardTitle className='text-xl'>Welcome back</CardTitle>
          <CardDescription>Sign in to your account to continue</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              e.stopPropagation();
              form.handleSubmit();
            }}
          >
            <div className='grid gap-6'>
              <div className='grid gap-3'>
                <form.Field
                  name="username"
                  validators={{
                    onChange: ({ value }) => 
                      !value ? "Email is required" : undefined,
                  }}
                >
                  {(field) => (
                    <>
                      <Label htmlFor='username'>Email</Label>
                      <Input
                        id='username'
                        type='email'
                        placeholder='m@example.com'
                        value={field.state.value}
                        onChange={(e) => field.handleChange(e.target.value)}
                        onBlur={field.handleBlur}
                        disabled={mutation.isPending}
                      />
                      {field.state.meta.errors ? (
                        <p className="text-sm text-destructive mt-1">
                          {field.state.meta.errors.join(", ")}
                        </p>
                      ) : null}
                    </>
                  )}
                </form.Field>
              </div>
              <div className='grid gap-3'>
                <form.Field
                  name="password"
                  validators={{
                    onChange: ({ value }) => 
                      !value ? "Password is required" : undefined,
                  }}
                >
                  {(field) => (
                    <>
                      <div className='flex items-center'>
                        <Label htmlFor='password'>Password</Label>
                        <a href='#' className='ml-auto text-sm underline-offset-4 hover:underline'>
                          Forgot your password?
                        </a>
                      </div>
                      <Input
                        id='password'
                        type='password'
                        value={field.state.value}
                        onChange={(e) => field.handleChange(e.target.value)}
                        onBlur={field.handleBlur}
                        disabled={mutation.isPending}
                      />
                      {field.state.meta.errors ? (
                        <p className="text-sm text-destructive mt-1">
                          {field.state.meta.errors.join(", ")}
                        </p>
                      ) : null}
                    </>
                  )}
                </form.Field>
              </div>
              
              {mutation.isError && (
                <div className="text-sm text-destructive text-center">
                  {mutation.error?.message || "An error occurred during login"}
                </div>
              )}
              
              <form.Subscribe
                selector={(state) => [state.canSubmit, state.isSubmitting]}
              >
                {([canSubmit, isSubmitting]) => (
                  <Button 
                    type='submit' 
                    className='w-full' 
                    disabled={!canSubmit || isSubmitting || mutation.isPending}
                  >
                    {mutation.isPending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Signing in...
                      </>
                    ) : (
                      "Sign in"
                    )}
                  </Button>
                )}
              </form.Subscribe>
            </div>
          </form>
        </CardContent>
      </Card>
      <div className='text-muted-foreground text-center text-xs text-balance'>
        Protected by enterprise-grade security
      </div>
    </div>
  );
}