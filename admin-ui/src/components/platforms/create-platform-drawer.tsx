import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerFooter,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Loader2 } from "lucide-react";
import { authenticatedFetch } from "@/lib/auth";
import { toast } from "sonner";

interface CreatePlatformDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

async function createPlatform(data: {
  name: string;
  description: string;
  is_active: boolean;
}) {
  const response = await authenticatedFetch("/v1/client_accounts/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ...data,
      is_platform_root: true,
    }),
  });
  
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to create platform");
  }
  
  return response.json();
}

export function CreatePlatformDrawer({ open, onOpenChange }: CreatePlatformDrawerProps) {
  const queryClient = useQueryClient();
  
  const createMutation = useMutation({
    mutationFn: createPlatform,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platforms"] });
      toast.success("Platform created successfully!");
      onOpenChange(false);
      form.reset();
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
  
  const form = useForm({
    defaultValues: {
      name: "",
      description: "",
      is_active: true,
    },
    onSubmit: async ({ value }) => {
      await createMutation.mutateAsync(value);
    },
  });
  
  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="w-full max-w-xl h-full flex flex-col">
        <DrawerHeader className="px-6">
          <DrawerTitle>Create New Platform</DrawerTitle>
          <DrawerDescription>
            Set up a new multi-tenant platform for your organization
          </DrawerDescription>
        </DrawerHeader>
        
        <div className="overflow-y-auto px-6 py-4 flex-1">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              e.stopPropagation();
              form.handleSubmit();
            }}
            className="space-y-6"
          >
            <form.Field
              name="name"
              validators={{
                onChange: ({ value }) => (!value ? "Platform name is required" : undefined),
              }}
            >
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="name">Platform Name</Label>
                  <Input
                    id="name"
                    placeholder="e.g., Real Estate Platform, Healthcare Platform"
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    onBlur={field.handleBlur}
                  />
                  <p className="text-xs text-muted-foreground">
                    A unique name to identify this platform
                  </p>
                  {field.state.meta.errors && (
                    <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                  )}
                </div>
              )}
            </form.Field>
            
            <form.Field name="description">
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    placeholder="Describe the purpose and scope of this platform"
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    onBlur={field.handleBlur}
                    rows={4}
                  />
                  <p className="text-xs text-muted-foreground">
                    Help others understand what this platform is for
                  </p>
                  {field.state.meta.errors && (
                    <p className="text-sm text-destructive">{field.state.meta.errors.join(", ")}</p>
                  )}
                </div>
              )}
            </form.Field>
            
            <form.Field name="is_active">
              {(field) => (
                <div className="flex items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <Label htmlFor="is_active">Active Status</Label>
                    <p className="text-sm text-muted-foreground">
                      Enable this platform immediately after creation
                    </p>
                  </div>
                  <Switch
                    id="is_active"
                    checked={field.state.value}
                    onCheckedChange={field.handleChange}
                  />
                </div>
              )}
            </form.Field>
          </form>
        </div>
        
        <DrawerFooter className="px-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
            {([canSubmit]) => (
              <Button
                type="submit"
                disabled={!canSubmit || createMutation.isPending}
                onClick={form.handleSubmit}
              >
                {createMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  "Create Platform"
                )}
              </Button>
            )}
          </form.Subscribe>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}