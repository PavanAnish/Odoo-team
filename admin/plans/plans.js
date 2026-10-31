import { crud } from '../shared/store.js';

export function plansView() {
  return crud('plans');
}
