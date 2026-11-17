from ortools.sat.python import cp_model

model = cp_model.CpModel()
x = model.NewBoolVar("x")
model.Add(x == 1)

solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 5
solver.parameters.num_search_workers = 1

status = solver.Solve(model)
print("Solver status:", solver.StatusName(status))

if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    print("Variable x:", solver.Value(x))
