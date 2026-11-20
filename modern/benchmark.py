"""Repeatable engine smoke benchmark; does not measure WebView responsiveness."""
import resource
from statistics import median
import time
from decimal import Decimal
from modern.backend.service import Service
from estimator.data.schedule import ResourceItemModel
s=Service()
s.model.resources['R']=ResourceItemModel('R','Long description\n'*20,'kg',Decimal('10.05'))
for i in range(10000):s.model.add_ana_res(['R',Decimal('1.25'),''],0)
s.model.ana_items[0]['_resource_ids'] = [str(i) for i in range(10000)]
timings=[]
for i in range(10):
    start=time.perf_counter();state=s.state();timings.append((time.perf_counter()-start)*1000)
print(f'10,000 resource rows: median state/evaluation {median(timings):.2f} ms; max RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss} KiB')
s.close()
