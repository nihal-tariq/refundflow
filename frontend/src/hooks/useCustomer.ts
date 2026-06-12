/** React Query hooks for customer data. */

import { useQuery } from "@tanstack/react-query";
import { fetchCustomer, fetchCustomers } from "@/api/refundApi";
import type { CustomerProfile } from "@/types";

/**
 * Fetch a single customer profile, cached by id.
 *
 * @param customerId - The customer id to fetch (query disabled when empty).
 */
export function useCustomer(customerId: string) {
  return useQuery<CustomerProfile>({
    queryKey: ["customer", customerId],
    queryFn: () => fetchCustomer(customerId),
    enabled: Boolean(customerId),
    retry: false,
  });
}

/** Fetch all demo customers for the picker. */
export function useCustomers() {
  return useQuery<CustomerProfile[]>({
    queryKey: ["customers"],
    queryFn: fetchCustomers,
    staleTime: 5 * 60 * 1000,
  });
}
