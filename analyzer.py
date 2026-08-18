# This is analyzer class for optimizer failures
from get_data import Get_Data

# TODO:
# * First we need to define the structure of the flow
# --- What is the data types (in and out)
# --- At which point we need to trigger
# --- Do we need to change objective function when we analyze
# --- Do we need to create route or just creating class or function is enough
# --- When we can apply the parallelization or serialization
# --- What will be the lambda function structure (how we gonna use it)
# * Second we need to define the most common infeasibility types
# --- Just no gap issue (this is the most common)
# --- No gap issue with min session and events for part 1
# --- Low percentage chosen by user (this is for part 2)
# --- No gap and unmatching issues
# --- Time constraints and unmatching constraints issues

# * Third we need to write scalable code for most common infeasibility types
# --- We need to write clear code with comments and fits into best practice
# * Finally we need to brute force or try all other combinations in order to define what is rule breaker
# --- Lets assume that none of most common infeasibility types worked so we gonna try all combinations
# --- When we trying all combinations how we gonna do that if there are n constraints then combinations will be 2^n and that is a lot
# --- We have to find a way to make sure we cover all possible combinations with less work load
# TODO:
class Analyzer:
  def __init__(self,payload):
    self.payload = payload
  def getConstraints(self):
    # some_data = Get_Data(self.payload)
    # print("analyze_mode_print1 : ",some_data.get_custom_constraints())
    pass
  def adjustPayload(self,modifiedDict):
    self.payload.update(modifiedDict)
    return self.payload
    pass
  def isNoGapRelatedIssues(self):
    return self.adjustPayload({"ignoredConstrainTypes":["gaps"]})
    pass
  def isSessionLengthRelatedIssues(self):
    pass
  def isTimeRelatedIssues(self):
    pass
  def isBreakQuantityRelatedIssues(self):
    pass
  def isCombinationOfConstraintsRelatedIssues(self):
    pass
  def bruteForce(self):
    pass






ss = Analyzer({})

print(ss.isNoGapRelatedIssues())