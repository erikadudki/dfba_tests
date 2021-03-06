import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt


def get_t_simu(data):
    measured_time = data.iloc[:, 0]
    if 'ime' not in data.columns[0]:
        raise ValueError('CAUTION!!! Check that time column, is called "Time" '
                         'or "time [...]", and the column should be the '
                         'second column in csv-format (1st column will be '
                         'read in as index column) \n '
                         '(data = pd.read_csv(data_dir, index_col=0))')
    t_start = measured_time.iloc[0]
    t_end = np.round(measured_time.iloc[-1],decimals=5)
    # minimal time steps
    t_steps = np.zeros(len(measured_time)-1)
    for i_st in range(len(measured_time)-1):
        t_steps[i_st] = measured_time.iloc[i_st+1]-measured_time.iloc[i_st]
    t_out = np.round(min(t_steps),decimals=5)

    return t_start, t_end, t_out


def get_obs_names(data):
    """get the names of the observables from the data table. Note, that the
    first column needs to be 'Time'!"""
    if 'ime' not in data.columns[0]:
        raise ValueError('CAUTION!!! Check that time column, is called "Time" '
                         'or "time [...]", and the column should be the '
                         'second column in csv-format (1st column will be '
                         'read in as index column) \n '
                         '(data = pd.read_csv(data_dir, index_col=0))')
    return data.columns[1:]


class ObjFunction:
    """
    The objective function class.
    Parameters
    ----------
    model:
        [dfba.model.DfbaModel]
    data:
        [pandas.Dataframe] 1st column has to be "time" column, rest of
        columns are observable measurements
    par_names:
        [list of strings] List of parameter names
    param_scale:
        [str] ("lin" | "log10") scale of the parameters for optimization
    cost_mod:
        [str] ("LS" | "NLLH") mode of objective function, either Least-Squares
        or negative-Log-Likelihood.
    """
    # define objective function: initialization with: model,
    # data (measured observables),
    # parameter_names,
    # parameter_scales ("lin"|"log10"),
    #
    # call the class with the parameters (np.array)
    # return cost of the objective function

    def __init__(self, model, data, par_names, param_scale, cost_mod):
        self.model = model
        # self.measured_observables = measured_observables
        self.data = data
        self.par_names = par_names
        self.param_scale = param_scale
        self.cost_mod = cost_mod

    def __call__(self, parameters):
        # transform log parameters to lin
        if self.param_scale == 'log10':
            self.parameters = 10**parameters
        elif self.param_scale == 'lin':
            self.parameters = parameters

        # Numpy parameters to dict
        par_dict = {}
        for i_p in range(len(self.par_names)):
            par_dict[self.par_names[i_p]] = self.parameters[i_p]

        # Create Sigma array # TODO
        obs_names = get_obs_names(self.data)
        if self.cost_mod == "NLLH":
            nr_obs = len(obs_names)
            sigma = np.zeros(nr_obs)
            for i_e, i_p in enumerate(range(len(self.par_names)-nr_obs,
                                            len(self.par_names))):
                sigma[i_e] = self.parameters[i_p]

        # get t_start, t_end, t_out from measured time
        t_start, t_end, t_out = get_t_simu(self.data)

        # Update Parameters
        # par_dict["K_g"] = 0.0027
        # par_dict["v_gmax"] = 10.5
        # par_dict["K_z"] = 0.0165
        # par_dict["v_zmax"] = 6.0
        # sigma[0] = 0.01
        # sigma[1] = 0.01
        # sigma[2] = 0.01
        print(par_dict)
        self.model.update_parameters(par_dict)
        t_end = t_end + t_out
        concentrations, trajectories = self.model.simulate(t_start, t_end,
                                                           t_out)

        # get subset of times, that are present in measurement times.
        indx = []
        for i in range(len(self.data['time'])):
            for j in range(len(concentrations['time'])):
                if np.isclose(concentrations['time'][j],
                              self.data['time'].values[i]):
                    indx.append(j)

        conc_subset = concentrations.iloc[indx]

        # check that first column is time:
        if 'time' not in self.data.columns[0]:
            raise ValueError('First column of the data needs to be "time"-'
                             'column! (= Second column in csv-file)')

        # to check!
        # check for exemplary observable (obs_names[0]) if simulation values
        # exist in last time points, if not copy last entries
        if len(conc_subset) < len(self.data):
            # copy last results into not simulated time points
            while len(conc_subset) < len(self.data):
                row_next = conc_subset[-1:].copy()
                row_next['time'] = self.data['time'].iloc[
                    len(conc_subset[obs_names[0]])]
                    # conc_subset['time'][-1:] + 1
                conc_subset = conc_subset.append(row_next,ignore_index=True)

        # check if length of found matched indices equals length of measurement
        # time
        if len(conc_subset) != len(self.data['time']):
            raise ValueError('Some time points are lost. Please check if '
                             'inferred t_out is correct, or why the found time'
                             ' subset does not match all measurement times.')

        if self.cost_mod == "LS":
            # Least squares
            cost = 0
            for i_obs in range(len(obs_names)):
                res = np.asarray(self.data[obs_names[i_obs]]) - \
                             np.asarray(conc_subset[obs_names[i_obs]])
                cost = cost + np.sum(np.power(res, 2))
                print(cost)

        elif self.cost_mod == "NLLH":
            # neg-log-likelihood TODO
            cost = 0
            for i_obs in range(0, len(obs_names)):
                # sigma = self.data[obs_names[i_obs]]  # TODO
                res = np.asarray(self.data[obs_names[i_obs]]) - \
                      np.asarray(conc_subset[obs_names[i_obs]])
                nllh_obs = np.log(2*np.pi*np.power(sigma[i_obs], 2)) + \
                    np.power((res/sigma[i_obs]), 2)
                cost = cost + 0.5*sum(nllh_obs)
            print(cost)

        else:
            raise ValueError("Choose which cost-function to use, either "
                             "'cost_mod='LS'' (Least-Squares) or "
                             "'cost_mod='NLLH''(negative log likelihood).")

        return cost
