import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useForm } from "@tanstack/react-form";
import { useMutation } from "@tanstack/react-query";
import { GalleryVerticalEnd } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

async function initializeSystem(values: { email: string; password: string }) {
  const response = await fetch("/v1/system/initialize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to initialize system");
  }

  return response.json();
}

export const Route = createFileRoute("/setup")({
  component: SetupComponent,
});

function SetupComponent() {
  const router = useRouter();

  const mutation = useMutation({
    mutationFn: initializeSystem,
    onSuccess: () => {
      // On successful creation, redirect to the login page
      router.navigate({ to: "/login" });
    },
  });

  const form = useForm({
    defaultValues: {
      email: "",
      password: "",
    },
    onSubmit: async ({ value }) => {
      mutation.mutate(value);
    },
  });

  return (
    <div className='bg-background flex min-h-svh flex-col items-center justify-center gap-6 p-6 md:p-10'>
      <div className='flex w-full max-w-sm flex-col gap-6'>
        <a href='#' className='flex items-center gap-2 self-center font-medium'>
          <div className='bg-primary text-primary-foreground flex size-6 items-center justify-center rounded-md'>
            <GalleryVerticalEnd className='size-4' />
          </div>
          Outlabs Auth
        </a>
        <Card>
          <CardHeader className='text-center'>
            <CardTitle className='text-xl'>System Setup</CardTitle>
            <CardDescription>Create the first Super Admin account to initialize the system</CardDescription>
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
                <form.Field
                  name='email'
                  validators={{
                    onChange: ({ value }) => {
                      if (!value) return "Email is required";
                      if (!/\S+@\S+\.\S+/.test(value)) return "Please enter a valid email address";
                      return undefined;
                    },
                  }}
                  children={(field) => (
                    <div className='grid gap-3'>
                      <Label htmlFor='email'>Admin Email</Label>
                      <Input
                        id='email'
                        type='email'
                        placeholder='admin@example.com'
                        value={field.state.value}
                        onBlur={field.handleBlur}
                        onChange={(e) => field.handleChange(e.target.value)}
                        required
                      />
                      {field.state.meta.errors ? <p className='text-sm font-medium text-destructive'>{field.state.meta.errors.join(", ")}</p> : null}
                    </div>
                  )}
                />
                <form.Field
                  name='password'
                  validators={{
                    onChange: ({ value }) => {
                      if (!value) return "Password is required";
                      if (value.length < 8) return "Password must be at least 8 characters";
                      return undefined;
                    },
                  }}
                  children={(field) => (
                    <div className='grid gap-3'>
                      <Label htmlFor='password'>Password</Label>
                      <Input
                        id='password'
                        type='password'
                        placeholder='Minimum 8 characters'
                        value={field.state.value}
                        onBlur={field.handleBlur}
                        onChange={(e) => field.handleChange(e.target.value)}
                        required
                      />
                      {field.state.meta.errors ? <p className='text-sm font-medium text-destructive'>{field.state.meta.errors.join(", ")}</p> : null}
                    </div>
                  )}
                />
                {mutation.isError && <p className='text-sm font-medium text-destructive'>{mutation.error.message}</p>}
                <form.Subscribe
                  selector={(state) => [state.canSubmit, state.isSubmitting]}
                  children={([canSubmit, isSubmitting]) => (
                    <Button type='submit' className='w-full' disabled={!canSubmit || isSubmitting}>
                      {isSubmitting || mutation.isPending ? "Initializing..." : "Initialize System"}
                    </Button>
                  )}
                />
              </div>
            </form>
          </CardContent>
        </Card>
        <div className='text-muted-foreground text-center text-xs text-balance'>This will create your first Super Admin account and complete the system setup.</div>
      </div>
    </div>
  );
}
