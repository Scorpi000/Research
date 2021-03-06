# coding=utf-8
"""理财规划"""
import logging

import numpy as np
import pandas as pd
from traits.api import HasTraits, Float, Instance, Range, Either, Bool, Enum

from RateSimulator import RateSimulator
from CashFlowCalculator import fv

class FinancialPlan(HasTraits):
    """理财规划"""
    def __init__(self, logger=None, **kwargs):
        if logger is None:
            self._Logger = logging.getLogger()
        else:
            self._Logger = logger
        for iTraitName in self.visible_traits():
            if iTraitName in kwargs:
                setattr(self, iTraitName, kwargs[iTraitName])
    # 计算方案的可行概率
    def calc_feasibility(self):
        pass
    # 计算累计本金投入
    def calc_cumulate_principal(self):
        pass
    # 计算账户剩余金额
    def calc_account_balance(self):
        pass

class PensionPlan(FinancialPlan):
    """养老规划"""
    CurrentAge = Range(low=1, high=200, value=30, visible_to_user=True, label="当前年龄")
    RetirementAge = Range(low=1, high=200, value=60, visible_to_user=True, label="退休年龄")
    FinalAge = Range(low=1, high=200, value=80, visible_to_user=True, label="终止年龄")
    Cost = Float(35000, visible_to_user=True, label="养老费用")
    CostGrowthRate = Float(0.0201, visible_to_user=True, label="费用增长率")
    PV = Float(100000, visible_to_user=True, label="初始投入")
    PeriodInvest = Float(20000, visible_to_user=True, label="每期投入")
    When = Enum("end", "begin", visible_to_user=True, label="定投时点")
    PreRetirementRate = Instance(RateSimulator, visible_to_user=True, label="退休前收益率")
    PostRetirementRate = Instance(RateSimulator, visible_to_user=True, label="退休后收益率")
    def __init__(self, logger=None, **kwargs):
        self.on_trait_change(self._on_instance_changed, "PreRetirementRate")
        self.on_trait_change(self._on_instance_changed, "PostRetirementRate")
        super().__init__(logger=logger, **kwargs)
        self._Rate = None# 收益率序列
        self._Pmt = None# 现金流序列
        self._FV = None# 终值序列
        for iTraitName in self.visible_traits():
            iTrait = self.trait(iTraitName)
            if iTrait.visible_to_user:
                self.on_trait_change(self._arg_changed, iTraitName)
    def _on_instance_changed(self, obj, name, old, new):
        if old is not None:
            for iTraitName in old.visible_traits():
                iTrait = old.trait(iTraitName)
                if iTrait.visible_to_user:
                    old.on_trait_change(self._arg_changed, iTraitName, remove=True)
        if new is not None:
            for iTraitName in new.visible_traits():
                iTrait = new.trait(iTraitName)
                if iTrait.visible_to_user:
                    new.on_trait_change(self._arg_changed, iTraitName)
    def _arg_changed(self):
        self._Rate = None
        self._Pmt = None
        self._FV = None
    def _init_data(self):
        if self._FV is not None:
            return 0
        PreRetirementNPeriod = self.RetirementAge - self.CurrentAge
        PostRetirementNPeriod = self.FinalAge - self.RetirementAge
        
        self.PreRetirementRate.NPeriod = PreRetirementNPeriod
        PreRetirementRate = self.PreRetirementRate.simulate()
        self.PostRetirementRate.NPeriod = PostRetirementNPeriod
        PostRetirementRate = self.PostRetirementRate.simulate()
        self._Rate = np.r_[PreRetirementRate, PostRetirementRate]
        
        PreRetirementPmt = np.full(shape=(PreRetirementNPeriod, ), fill_value=-self.PeriodInvest)
        PostRetirementPmt = self.Cost * (1 + self.CostGrowthRate) ** (PreRetirementNPeriod + np.arange(0, PostRetirementNPeriod))
        self._Pmt = np.r_[PreRetirementPmt, PostRetirementPmt]
        
        self._FV = fv(rate=self._Rate, pmt=self._Pmt, pv=-self.PV, when=self.When, output="multi")
        return 0
    def calc_feasibility(self):
        self._init_data()
        Mask = np.all(self._FV >= 0, axis=0)
        return np.sum(Mask) / np.size(Mask)
    def calc_cumulate_principal(self):
        self._init_data()
        Pmt = np.r_[-self.PV, self._Pmt]
        Pmt = np.clip(Pmt, -np.inf, 0)
        return np.cumsum(-Pmt, axis=0)
    def calc_account_balance(self):
        self._init_data()
        FV = np.copy(self._FV)
        NPeriod, NSample = FV.shape
        Idx = np.arange(NPeriod)
        TargetIdx = np.apply_along_axis(lambda m: (np.min(Idx[m]) if np.sum(m)>0 else -1), 0, (FV <= 0))
        Mask = ((np.repeat(np.expand_dims(Idx, 1), NSample, axis=1) > TargetIdx) & (TargetIdx > 0))
        FV[Mask] = np.repeat(np.expand_dims(FV[TargetIdx, np.arange(NSample)], 0), NPeriod, axis=0)[Mask]
        return FV

class HousePurchasePlan(FinancialPlan):
    """购房规划"""
    PreYearNum = Range(low=1, high=200, value=10, visible_to_user=True, label="购房前年数")
    DownPayment = Float(1000000, visible_to_user=True, label="首付金额")
    LoanAmount = Float(1400000, visible_to_user=True, label="贷款金额")
    LoanTerm = Range(low=1, high=200, value=30, visible_to_user=True, label="贷款年限")
    LoanRate = Float(0.05, visible_to_user=True, label="贷款年利率")
    LoanType = Enum("等额本息", "等额本金", visible_to_user=True, label="偿还方式")
    PV = Float(500000, visible_to_user=True, label="初始投入")
    PeriodPerYear = Range(low=1, high=200, value=12, visible_to_user=True, label="每年期数")
    When = Enum("end", "begin", visible_to_user=True, label="定投时点")
    PrePurchaseRate = Instance(RateSimulator, visible_to_user=True, label="购房前收益率")
    PostPurchaseRate = Instance(RateSimulator, visible_to_user=True, label="购房后收益率")
    PrePeriodInvest = Float(8000, visible_to_user=True, label="购房前每期投入")
    PostPeriodInvest = Float(5000, visible_to_user=True, label="购房后每期投入")
    def __init__(self, logger=None, **kwargs):
        self.on_trait_change(self._on_instance_changed, "PrePurchaseRate")
        self.on_trait_change(self._on_instance_changed, "PostPurchaseRate")
        super().__init__(logger=logger, **kwargs)
        self._Rate = None# 收益率序列
        self._NegPmt = None# 负向现金流序列
        self._PosPmt = None# 正向现金流序列
        self._FV = None# 终值序列
        for iTraitName in self.visible_traits():
            iTrait = self.trait(iTraitName)
            if iTrait.visible_to_user:
                self.on_trait_change(self._arg_changed, iTraitName)
    def _on_instance_changed(self, obj, name, old, new):
        if old is not None:
            for iTraitName in old.visible_traits():
                iTrait = old.trait(iTraitName)
                if iTrait.visible_to_user:
                    old.on_trait_change(self._arg_changed, iTraitName, remove=True)
        if new is not None:
            for iTraitName in new.visible_traits():
                iTrait = new.trait(iTraitName)
                if iTrait.visible_to_user:
                    new.on_trait_change(self._arg_changed, iTraitName)
    def _arg_changed(self):
        self._Rate = None
        self._NegPmt = None
        self._PosPmt = None
        self._FV = None
    def _init_data(self):
        if self._FV is not None:
            return 0
        PreNPeriod = self.PreYearNum * self.PeriodPerYear
        PostNPeriod = self.LoanTerm * self.PeriodPerYear
        
        self.PrePurchaseRate.NPeriod = PreNPeriod
        PrePurchaseRate = self.PrePurchaseRate.simulate()
        self.PostPurchaseRate.NPeriod = PostNPeriod
        PostPurchaseRate = self.PostPurchaseRate.simulate()
        self._Rate = np.r_[PrePurchaseRate, PostPurchaseRate]
        
        self._NegPmt = np.r_[np.full(shape=(PreNPeriod, ), fill_value=-self.PrePeriodInvest), np.full(shape=(PostNPeriod, ), fill_value=-self.PostPeriodInvest)]
        LoanRate = self.LoanRate / self.PeriodPerYear
        if self.LoanType == "等额本息":
            self._PosPmt = np.r_[np.zeros(shape=(PreNPeriod - 1, )), self.LoanAmount, np.full(shape=(PostNPeriod, ), fill_value=self.LoanAmount * LoanRate * (1 + LoanRate) ** PostNPeriod / ((1 + LoanRate)**PostNPeriod - 1))]
        elif self.LoanType == "等额本金":
            self._PosPmt = np.r_[np.zeros(shape=(PreNPeriod - 1, )), self.LoanAmount, (self.LoanAmount - (np.arange(1, PostNPeriod+1) - 1) * self.LoanAmount / PostNPeriod) * LoanRate + self.LoanAmount / PostNPeriod]
        else:
            raise Exception("'%s' is an unrecognized kind of loan type!" % (self.LoanType, ))
        self._FV = fv(rate=self._Rate, pmt=self._PosPmt + self._NegPmt, pv=-self.PV, when=self.When, output="multi")
        return 0
    def calc_feasibility(self):
        self._init_data()
        Mask = np.all(self._FV >= 0, axis=0)
        return np.sum(Mask) / np.size(Mask)
    def calc_cumulate_principal(self):
        self._init_data()
        Pmt = np.r_[-self.PV, self._NegPmt]
        Pmt = np.clip(Pmt, -np.inf, 0)
        return np.cumsum(-Pmt, axis=0)
    def calc_account_balance(self):
        self._init_data()
        FV = np.copy(self._FV)
        NPeriod, NSample = FV.shape
        Idx = np.arange(NPeriod)
        TargetIdx = np.apply_along_axis(lambda m: (np.min(Idx[m]) if np.sum(m)>0 else -1), 0, (FV <= 0))
        Mask = ((np.repeat(np.expand_dims(Idx, 1), NSample, axis=1) > TargetIdx) & (TargetIdx > 0))
        FV[Mask] = np.repeat(np.expand_dims(FV[TargetIdx, np.arange(NSample)], 0), NPeriod, axis=0)[Mask]
        return FV