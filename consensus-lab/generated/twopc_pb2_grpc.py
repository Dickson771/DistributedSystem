# Generated manually to avoid grpc_tools dependency
import grpc

import grpc

import generated.twopc_pb2 as twopc__pb2


class TwoPhaseCommitStub(object):
    def __init__(self, channel):
        self.VoteRequest = channel.unary_unary(
            "/twopc.TwoPhaseCommit/VoteRequest",
            request_serializer=twopc__pb2.VoteRequestMessage.SerializeToString,
            response_deserializer=twopc__pb2.VoteResponseMessage.FromString,
        )
        self.Decision = channel.unary_unary(
            "/twopc.TwoPhaseCommit/Decision",
            request_serializer=twopc__pb2.DecisionRequest.SerializeToString,
            response_deserializer=twopc__pb2.DecisionAck.FromString,
        )


class TwoPhaseCommitServicer(object):
    def VoteRequest(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def Decision(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")


def add_TwoPhaseCommitServicer_to_server(servicer, server):
    rpc_method_handlers = {
        "VoteRequest": grpc.unary_unary_rpc_method_handler(
            servicer.VoteRequest,
            request_deserializer=twopc__pb2.VoteRequestMessage.FromString,
            response_serializer=twopc__pb2.VoteResponseMessage.SerializeToString,
        ),
        "Decision": grpc.unary_unary_rpc_method_handler(
            servicer.Decision,
            request_deserializer=twopc__pb2.DecisionRequest.FromString,
            response_serializer=twopc__pb2.DecisionAck.SerializeToString,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        "twopc.TwoPhaseCommit", rpc_method_handlers
    )
    server.add_generic_rpc_handlers((generic_handler,))


__all__ = [
    "TwoPhaseCommitStub",
    "TwoPhaseCommitServicer",
    "add_TwoPhaseCommitServicer_to_server",
]
