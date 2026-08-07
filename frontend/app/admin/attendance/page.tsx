"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, Box, Flex, SegmentedControl, Text, Tooltip } from "@radix-ui/themes";

import { AppShell } from "@/components/AppShell";
import type { Column } from "@/components/DataTable";
import { GroupedTable, type GroupNode } from "@/components/GroupedTable";
import { useUrlFilters } from "@/hooks/useUrlFilters";
import { api } from "@/lib/api";
import type { AttendanceGroup, AttendanceReport, AttendanceUserRow, Timeframe } from "@/lib/types";

// Each row carries its group's scheduled days so the Record cell can render the full strip
// (GroupedTable columns are fixed table-wide; the days differ per group).
type Row = AttendanceUserRow & { days: string[] };

const TIMEFRAMES: { value: Timeframe; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "week", label: "This week" },
  { value: "semester", label: "Since semester start" },
];

function toNode(group: AttendanceGroup, timeframe: Timeframe): GroupNode<Row> {
  const missingSemester = timeframe === "semester" && group.semester_start === null;
  return {
    id: group.group_id ?? "__none__",
    title: group.group_name,
    meta: missingSemester
      ? "no semester start set"
      : `${group.days.length} scheduled day${group.days.length === 1 ? "" : "s"}`,
    children: group.children.map((child) => toNode(child, timeframe)),
    rows: group.users.map((u) => ({ ...u, days: group.days })),
  };
}

function RecordCell({ row }: { row: Row }) {
  if (row.days.length === 0) {
    return (
      <Text size="1" color="gray">
        —
      </Text>
    );
  }
  if (row.days.length === 1) {
    const present = row.present.includes(row.days[0]);
    return <Badge color={present ? "green" : "red"}>{present ? "Present" : "Absent"}</Badge>;
  }
  return (
    <Flex gap="1" wrap="wrap">
      {row.days.map((day) => {
        const present = row.present.includes(day);
        return (
          <Tooltip key={day} content={`${day} — ${present ? "Present" : "Absent"}`}>
            <Box
              width="10px"
              height="10px"
              style={{
                borderRadius: 2,
                background: present ? "var(--green-9)" : "var(--red-9)",
              }}
            />
          </Tooltip>
        );
      })}
    </Flex>
  );
}

export default function AttendancePage() {
  const [timeframe, setTimeframe] = useState<Timeframe>("today");
  const [report, setReport] = useState<AttendanceReport | null>(null);

  const load = useCallback(async () => {
    setReport(await api.attendance(timeframe));
  }, [timeframe]);

  const hydrated = useUrlFilters({
    decode: (sp) => {
      const t = sp.get("timeframe");
      if (t === "today" || t === "week" || t === "semester") setTimeframe(t);
    },
    params: { timeframe: timeframe === "today" ? undefined : timeframe },
  });

  useEffect(() => {
    if (hydrated) load();
  }, [hydrated, load]);

  const columns: Column<Row>[] = [
    { header: "Name", cell: (r) => r.name },
    { header: "Record", cell: (r) => <RecordCell row={r} /> },
    { header: "Present", cell: (r) => r.present_count },
    { header: "Absent", cell: (r) => (r.absent_count > 0 ? r.absent_count : "—") },
  ];

  return (
    <AppShell>
      <Flex mb="3" justify="between" align="center" wrap="wrap" gap="3">
        <SegmentedControl.Root
          value={timeframe}
          onValueChange={(v) => setTimeframe(v as Timeframe)}
        >
          {TIMEFRAMES.map((t) => (
            <SegmentedControl.Item key={t.value} value={t.value}>
              {t.label}
            </SegmentedControl.Item>
          ))}
        </SegmentedControl.Root>
        {report && (
          <Text size="1" color="gray">
            Days are counted in the {report.timezone} time zone. A day is scheduled for a group
            when anyone in it checked in.
          </Text>
        )}
      </Flex>

      <GroupedTable
        columns={columns}
        groups={(report?.groups ?? []).map((g) => toNode(g, timeframe))}
        rowKey={(r) => r.user_id}
        empty="No attendance recorded yet — it's logged automatically on a user's first kiosk scan of the day."
      />
    </AppShell>
  );
}
