import sys, multiprocessing
import numpy as np
from collections import OrderedDict
from pyqtgraph import toposort


# TODO: for now, we define one "unit of work" as being the work done by one AnalysisModule for one whole experiment.
# BUT: some higher-level modules will aggregate results from across many experiments, so we will need to rethink
# the unit of work definition at that point.

class AnalysisModule(object):
    """Analysis modules represent analysis tasks that can be run independently of other parts of the analysis
    pipeline. 
    
    For any given experiment, a sequence of analysis stages must be processed in order. Each of these requires a specific
    set of inputs to be present, and produces/stores some output. Inputs and outputs can be raw data files, database tables,
    etc., although outputs are probably always written into a database. Each AnalysisModule subclass represents a single stage
    in the sequence of analyses that occur across a pipeline.
    
    From here, we should be able to:
    - Ask for which experiments this analysis has already been run (and when)
    - Ask for which experiments this analysis needs to be run (input dependencies are met and no result exists yet or is out of date)    
    - Run and store analysis for any specific experiment
    - Remove / re-run analysis for any specific experiment
    - Remove / re-run analysis for all experiments (for example, after a code change affecting all analysis results)
    - Initialize storage for analysis results (create DB tables, empty folders, etc.)
    
    Note that AnalysisModule classes generally need not implement any actual _analysis_; rather, they are simply responsible for
    data _management_ within the analysis pipeline. When an AnalysisModule is asked to update an analysis result, it may call out to
    other packages to do the real work.
    """    
    
    name = None
    dependencies = []

    @staticmethod
    def all_modules():
        subclasses = AnalysisModule.__subclasses__()
        deps = {c:c.dependencies for c in subclasses}
        return OrderedDict([(mod.name, mod) for mod in toposort(deps)])
    
    @classmethod
    def dependent_modules(cls):
        mods = cls.all_modules()
        return [mod for mod in mods if cls in mod.dependencies]
    
    @classmethod
    def update(cls, experiment_ids=None, limit=None, parallel=False, workers=None, raise_exceptions=False):
        """Update analysis results for this module.
        
        Parameters
        ----------
        experiment_ids : list | None
            List of experiment IDs to be updated, or None to update all experiments.
        parallel : bool
            If True, run jobs in parallel threads or subprocesses.
        workers : int or None
            Number of parallel workers to spawn. If None, then use one worker per CPU core.
        limit : int | None
            Maximum number of jobs to process (or None to disable this limit).
            If limit is enabled, then jobs are randomly shuffled before selecting the limited subset.
        raise_exceptions : bool
            If True, then exceptions are raised and will end any further processing.
            If False, then errors are logged and ignored.
            This is used mainly for debugging to allow traceback inspection.
        """
        if experiment_ids is None:
            finished, invalid, ready = cls.job_summary()
            experiment_ids = sorted(invalid + ready, reverse=True)
            if limit is not None:
                np.random.shuffle(experiment_ids)
                experiment_ids = experiment_ids[:limit]

        jobs = [(expt_id, (expt_id in invalid), i, len(experiment_ids)) for i, expt_id in enumerate(experiment_ids)]

        if parallel:
            pool = multiprocessing.Pool(processes=workers)
            pool.map(cls._run_job, jobs)
        else:
            for job in jobs:
                cls._run_job(job, raise_exceptions=raise_exceptions)

    @classmethod
    def _run_job(cls, job, raise_exceptions=False):
        """Entry point for running a single analysis job; may be invoked in a subprocess.
        """
        experiment_id, invalid, job_index, n_jobs = job
        print("Processing %d/%d  %s") % (job_index, n_jobs, experiment_id)
        try:
            cls.process_experiment(experiment_id, invalid)
        except Exception as exc:
            if raise_exceptions:
                raise
            else:
                print("Error processing %d/%d  %s:") % (job_index, n_jobs, experiment_id)
                sys.excepthook(*sys.exc_info())
        else:
            print("Finished %d/%d  %s") % (job_index, n_jobs, experiment_id)
    
    @classmethod
    def process_experiment(cls, experiment_id, invalid):
        """Process analysis for one experiment.
        
        Parameters
        ----------
        experiment_id :
            The ID of the experiment to be processed.
        invalid : bool
            If True, then previous (invalid) results already exist and
            need to be either purged or updated.
        
        Must be reimplemented in subclasses.
        """
        raise NotImplementedError()
        
    @classmethod
    def finished_jobs(cls):
        """Return an ordered dict of job IDs that have been processed by this module and
        the dates when they were processed.

        Note that some results returned may be obsolete if dependencies have changed.
        """
        raise NotImplementedError()

    @classmethod
    def drop_jobs(cls, experiment_ids):
        """Remove all results previously stored for a list of experiment IDs.
        """
        raise NotImplementedError()

    @classmethod
    def drop_all(cls):
        """Remove all results generated by this module.
        """
        raise NotImplementedError()

    @classmethod
    def job_summary(cls):
        """Return information about jobs that have (not) been processed.
        
        Returns
        -------
        finished : list
            List of experiment IDs that have finished, valid results
        invalid : list
            List of experiment IDs that have finished, invalid results
        ready : list
            List of experiment IDs that have no result but are ready to be processed
        """
        my_finished = cls.finished_jobs()
        dep_finished = cls.dependent_finished_jobs()
        
        finished = []
        invalid = []
        ready = []
        
        all_jobs = sorted(list(set(list(my_finished.keys()) + list(dep_finished.keys()))))
        
        for job in all_jobs:
            if job in my_finished:
                if job not in dep_finished or dep_finished[job] > date:
                    invalid.append(job)
                else:
                    finished.append(job)
            else:
                ready.append(job)
                
        return finished, invalid, ready

    @classmethod
    def dependent_finished_jobs(self):
        """Return an ordered dict of all jobs that have been completed by dependencies
        and the dates they were processed.
        """
        jobs = OrderedDict()
        for i,dep in enumerate(cls.dependencies):
            dep_finished = dep.finished_jobs()
            for k,v in dep_finished.items():
                jobs.setdefault(k, []).append(v)
        
        finished = OrderedDict()
        for job, dates in jobs.items():
            if len(dates) < len(cls.dependencies):
                # not all dependencies are finished yet
                continue
            finished[job] = max(dates)

        return finished
