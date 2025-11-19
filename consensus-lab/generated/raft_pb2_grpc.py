import grpc

import generated.raft_pb2 as raft__pb2


class RaftStub(object):
    def __init__(self, channel):
        self.RequestVote = channel.unary_unary(
            "/raft.Raft/RequestVote",
            request_serializer=raft__pb2.RequestVoteRequest.SerializeToString,
            response_deserializer=raft__pb2.RequestVoteResponse.FromString,
        )
        self.AppendEntries = channel.unary_unary(
            "/raft.Raft/AppendEntries",
            request_serializer=raft__pb2.AppendEntriesRequest.SerializeToString,
            response_deserializer=raft__pb2.AppendEntriesResponse.FromString,
        )
        self.ClientRequest = channel.unary_unary(
            "/raft.Raft/ClientRequest",
            request_serializer=raft__pb2.ClientOperation.SerializeToString,
            response_deserializer=raft__pb2.ClientResponse.FromString,
        )


class RaftServicer(object):
    def RequestVote(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def AppendEntries(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def ClientRequest(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")


def add_RaftServicer_to_server(servicer, server):
    rpc_method_handlers = {
        "RequestVote": grpc.unary_unary_rpc_method_handler(
            servicer.RequestVote,
            request_deserializer=raft__pb2.RequestVoteRequest.FromString,
            response_serializer=raft__pb2.RequestVoteResponse.SerializeToString,
        ),
        "AppendEntries": grpc.unary_unary_rpc_method_handler(
            servicer.AppendEntries,
            request_deserializer=raft__pb2.AppendEntriesRequest.FromString,
            response_serializer=raft__pb2.AppendEntriesResponse.SerializeToString,
        ),
        "ClientRequest": grpc.unary_unary_rpc_method_handler(
            servicer.ClientRequest,
            request_deserializer=raft__pb2.ClientOperation.FromString,
            response_serializer=raft__pb2.ClientResponse.SerializeToString,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        "raft.Raft", rpc_method_handlers
    )
    server.add_generic_rpc_handlers((generic_handler,))


__all__ = [
    "RaftStub",
    "RaftServicer",
    "add_RaftServicer_to_server",
]
