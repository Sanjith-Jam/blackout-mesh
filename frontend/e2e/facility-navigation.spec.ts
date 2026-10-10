import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const fixture = (name: string) => JSON.parse(readFileSync(new URL(`../src/test/fixtures/${name}.json`, import.meta.url), 'utf8'));
const classrooms = fixture('classrooms');
const hospital = fixture('hospital');

test('classroom and hospital visualizers stay distinct while navigating', async ({ page }) => {
  await page.route('**/api/v1/visualizers/classrooms', route => route.fulfill({ json: classrooms }));
  await page.route('**/api/v1/visualizers/hospital', route => route.fulfill({ json: hospital }));

  await page.goto('/classrooms');
  await expect(page.getByRole('region', { name: 'Classroom floor plans' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Classroom power state' })).toBeVisible();

  await page.getByRole('link', { name: 'Hospital' }).click();
  await expect(page.getByRole('region', { name: 'Hospital floor plans' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Hospital power state' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Classroom floor plans' })).toHaveCount(0);

  await page.getByRole('link', { name: 'Classrooms' }).click();
  await expect(page.getByRole('region', { name: 'Classroom floor plans' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Hospital floor plans' })).toHaveCount(0);
});
